import numpy as np
import pandas as pd
from scipy.signal import butter, filtfilt
from collections import defaultdict


COLUMN_MAP = {
    'trip_id':   'trip_id',
    'timestamp': 'elapsed_seconds',
    'ax':        'accel_x',
    'ay':        'accel_y',
    'az':        'accel_z',
    'speed':     'speed_kmh',
    'lat':       'gps_lat',
    'lon':       'gps_lon',
}


TRIP_ID_COLUMN = COLUMN_MAP['trip_id']


FS = 1
MIN_SPEED_KMH = 5.0

ACC_THRESHOLD   = 3.4
BRAKE_THRESHOLD = 4.4
TURN_THRESHOLD  = 3.9

TZ = 2.0
TS = 0.05
POTHOLE_MIN_CONFIDENCE = 0.40

MERGE_GAP_SEC = 3.0
GPS_CLUSTER_RADIUS = 0.0005


def lowpass_filter(signal, cutoff=0.3):
    nyq = FS / 2.0
    if cutoff >= nyq or len(signal) < 15:
        return signal
    b, a = butter(2, cutoff / nyq, btype='low')
    return filtfilt(b, a, signal, axis=0)


def remove_gravity(az, speed):
    stationary = speed < 2.0
    gravity = np.mean(az[stationary]) if stationary.sum() >= 3 else 9.81
    return az - gravity


def adaptive_threshold(signal, k=2.5, base=2.0):
    return max(base, float(np.mean(np.abs(signal)) + k * np.std(np.abs(signal))))


def compute_motion_score(value, threshold):
    return round(min(1.0, (value / threshold) * 0.5), 3)


def detect_behaviour(ax_lp, ay_lp, speed, timestamps, gps_lat, gps_lon, trip_id):
    events = []

    for i in range(len(ax_lp)):
        spd = float(speed[i])
        if spd < MIN_SPEED_KMH:
            continue

        ax_val    = float(ax_lp[i])
        ay_val    = float(ay_lp[i])
        ts        = float(timestamps[i])
        lat       = float(gps_lat[i])
        lon       = float(gps_lon[i])
        magnitude = round(float(np.sqrt(ax_val**2 + ay_val**2)), 3)

        if ax_val > ACC_THRESHOLD:
            score = compute_motion_score(ax_val, ACC_THRESHOLD)
            events.append({'trip_id': trip_id, 'timestamp': ts, 'sample_idx': i,
                           'lat': lat, 'lon': lon, 'speed_kmh': spd,
                           'label': 'sudden_acceleration', 'value': magnitude,
                           'motion_score': score, 'note': ''})

        if ax_val < -BRAKE_THRESHOLD:
            score = compute_motion_score(abs(ax_val), BRAKE_THRESHOLD)
            events.append({'trip_id': trip_id, 'timestamp': ts, 'sample_idx': i,
                           'lat': lat, 'lon': lon, 'speed_kmh': spd,
                           'label': 'sudden_brake', 'value': magnitude,
                           'motion_score': score, 'note': ''})

        if abs(ay_val) > TURN_THRESHOLD:
            score = compute_motion_score(abs(ay_val), TURN_THRESHOLD)
            events.append({'trip_id': trip_id, 'timestamp': ts, 'sample_idx': i,
                           'lat': lat, 'lon': lon, 'speed_kmh': spd,
                           'label': 'sharp_turn', 'value': magnitude,
                           'motion_score': score, 'note': ''})

    return events


def detect_potholes(az_raw, speed, timestamps, gps_lat, gps_lon, trip_id):
    events = []
    tz_adaptive = adaptive_threshold(az_raw, k=2.5, base=TZ)

    for i in range(len(az_raw)):
        spd   = float(speed[i])
        z_abs = abs(float(az_raw[i]))

        if spd < MIN_SPEED_KMH:
            continue
        if z_abs < tz_adaptive:
            continue
        if z_abs < TS * spd:
            continue

        z_score    = min(1.0, z_abs / tz_adaptive)
        spd_score  = min(1.0, z_abs / max(TS * spd, 0.01))
        confidence = round((z_score * 0.7 + spd_score * 0.3), 3)

        if confidence < POTHOLE_MIN_CONFIDENCE:
            continue

        motion_score = compute_motion_score(z_abs, tz_adaptive)
        events.append({'trip_id': trip_id, 'timestamp': float(timestamps[i]),
                       'sample_idx': i, 'lat': float(gps_lat[i]), 'lon': float(gps_lon[i]),
                       'speed_kmh': spd, 'label': 'pothole', 'value': round(z_abs, 3),
                       'motion_score': motion_score, 'note': 'pothole present'})

    return events



def merge_nearby_events(events, merge_gap_sec=MERGE_GAP_SEC):
    if not events:
        return []

    behaviour_labels = {'sudden_acceleration', 'sudden_brake', 'sharp_turn'}
    behaviour = sorted([e for e in events if e['label'] in behaviour_labels],
                       key=lambda e: e['timestamp'])
    road = [e for e in events if e['label'] not in behaviour_labels]

    merged = []
    i = 0
    while i < len(behaviour):
        anchor = behaviour[i]
        burst  = [anchor]
        j = i + 1
        while j < len(behaviour):
            cand = behaviour[j]
            if cand['label'] == anchor['label'] and (cand['timestamp'] - burst[-1]['timestamp']) <= merge_gap_sec:
                burst.append(cand)
                j += 1
            else:
                break

        if len(burst) == 1:
            merged.append(anchor)
        else:
            best     = max(burst, key=lambda e: e['motion_score'])
            duration = burst[-1]['timestamp'] - burst[0]['timestamp']
            merged.append({'trip_id': anchor['trip_id'], 'timestamp': anchor['timestamp'],
                           'sample_idx': anchor['sample_idx'], 'lat': anchor['lat'],
                           'lon': anchor['lon'],
                           'speed_kmh': float(np.mean([e['speed_kmh'] for e in burst])),
                           'label': anchor['label'], 'value': best['value'],
                           'motion_score': best['motion_score'],
                           'note': f"merged {len(burst)} samples · duration {duration:.0f}s"})
        i = j

    all_events = merged + road
    all_events.sort(key=lambda e: e['timestamp'])
    return all_events


def deduplicate_potholes(all_events):
    pothole_events = [e for e in all_events if e['label'] == 'pothole']
    if not pothole_events:
        return []

    clusters = defaultdict(list)
    for e in pothole_events:
        lat_cell = round(e['lat'] / GPS_CLUSTER_RADIUS) * GPS_CLUSTER_RADIUS
        lon_cell = round(e['lon'] / GPS_CLUSTER_RADIUS) * GPS_CLUSTER_RADIUS
        clusters[(lat_cell, lon_cell)].append(e)

    result = []
    for (lat, lon), cluster_events in clusters.items():
        n_trips       = len(set(e['trip_id'] for e in cluster_events))
        mean_conf     = float(np.mean([e['motion_score'] for e in cluster_events]))
        combined_conf = round(1.0 - (1.0 - mean_conf) ** n_trips, 3)
        result.append({'lat': round(lat, 6), 'lon': round(lon, 6),
                       'n_trips': n_trips, 'confidence': combined_conf,
                       'pothole_present': True})

    return sorted(result, key=lambda x: x['confidence'], reverse=True)



def process_trip(trip_df, trip_id):
    c          = COLUMN_MAP
    ax         = trip_df[c['ax']].to_numpy(dtype=float)
    ay         = trip_df[c['ay']].to_numpy(dtype=float)
    az         = trip_df[c['az']].to_numpy(dtype=float)
    speed      = trip_df[c['speed']].to_numpy(dtype=float)
    timestamps = trip_df[c['timestamp']].to_numpy(dtype=float)
    gps_lat    = trip_df[c['lat']].to_numpy(dtype=float)
    gps_lon    = trip_df[c['lon']].to_numpy(dtype=float)

    az_clean = remove_gravity(az, speed)
    ax_lp    = lowpass_filter(ax)
    ay_lp    = lowpass_filter(ay)

    behaviour_events = detect_behaviour(ax_lp, ay_lp, speed, timestamps, gps_lat, gps_lon, trip_id)
    pothole_events   = detect_potholes(az_clean, speed, timestamps, gps_lat, gps_lon, trip_id)
    all_events       = merge_nearby_events(behaviour_events + pothole_events)

    return {'trip_id': trip_id, 'total_events': len(all_events), 'events': all_events}



def process_all_trips(trip_list):
    """
    Process a list of trip dicts (or a DataFrame) and return a combined result dict.

    Returns:
        {
            'trip_results':  [ {trip_id, total_events, events}, ... ],
            'all_events':    [ flat list of all events across trips ],
            'pothole_map':   [ deduplicated pothole locations ],
            'total_trips':   int,
            'total_events':  int,
        }
    """
    # Accept a raw DataFrame as input too
    if isinstance(trip_list, pd.DataFrame):
        df = trip_list
        if TRIP_ID_COLUMN and TRIP_ID_COLUMN in df.columns:
            trip_list = []
            for tid, g in df.groupby(TRIP_ID_COLUMN):
                trip_list.append({
                    'trip_id':        tid,
                    'timestamps':     g[COLUMN_MAP['timestamp']].tolist(),
                    'acceleration_x': g[COLUMN_MAP['ax']].tolist(),
                    'acceleration_y': g[COLUMN_MAP['ay']].tolist(),
                    'acceleration_z': g[COLUMN_MAP['az']].tolist(),
                    'speed_kmh':      g[COLUMN_MAP['speed']].tolist(),
                    'gps_lat':        g[COLUMN_MAP['lat']].tolist(),
                    'gps_lon':        g[COLUMN_MAP['lon']].tolist(),
                })
        else:
            trip_list = [{
                'trip_id':        'TRIP001',
                'timestamps':     df[COLUMN_MAP['timestamp']].tolist(),
                'acceleration_x': df[COLUMN_MAP['ax']].tolist(),
                'acceleration_y': df[COLUMN_MAP['ay']].tolist(),
                'acceleration_z': df[COLUMN_MAP['az']].tolist(),
                'speed_kmh':      df[COLUMN_MAP['speed']].tolist(),
                'gps_lat':        df[COLUMN_MAP['lat']].tolist(),
                'gps_lon':        df[COLUMN_MAP['lon']].tolist(),
            }]

    all_events_combined = []
    trip_results        = []

    for trip in trip_list:
        trip_id = trip.get('trip_id', 'UNKNOWN')

        # Build a small DataFrame so process_trip can reuse existing logic
        trip_df = pd.DataFrame({
            COLUMN_MAP['ax']:        trip['acceleration_x'],
            COLUMN_MAP['ay']:        trip['acceleration_y'],
            COLUMN_MAP['az']:        trip['acceleration_z'],
            COLUMN_MAP['speed']:     trip['speed_kmh'],
            COLUMN_MAP['timestamp']: trip['timestamps'],
            COLUMN_MAP['lat']:       trip['gps_lat'],
            COLUMN_MAP['lon']:       trip['gps_lon'],
        })

        result = process_trip(trip_df, trip_id)
        all_events_combined.extend(result['events'])
        trip_results.append(result)

    pothole_map = deduplicate_potholes(all_events_combined)

    return {
        'trip_results': trip_results,
        'all_events':   all_events_combined,
        'pothole_map':  pothole_map,
        'total_trips':  len(trip_results),
        'total_events': len(all_events_combined),
    }


LABEL_NAMES = {
    'sudden_brake':        'Sudden Brake',
    'sudden_acceleration': 'Sudden Acceleration',
    'sharp_turn':          'Sharp Turn',
    'pothole':             'Pothole',
}

def format_flags(result):
    """
    Accepts the dict returned by process_all_trips and returns a
    formatted string summary of all trips and pothole locations.
    """
    lines = []

    for trip_result in result['trip_results']:
        lines.append(f"\n  Trip: {trip_result['trip_id']}  |  Events: {trip_result['total_events']}")
        lines.append(f"  {'-'*51}")

        if not trip_result['events']:
            lines.append("  No events detected.")
            continue

        for e in sorted(trip_result['events'], key=lambda x: x['timestamp']):
            name = LABEL_NAMES.get(e['label'], e['label'])
            if e['label'] == 'pothole':
                lines.append(
                    f"  [t={e['timestamp']:5.0f}s]  {name:<22}|  z: {e['value']:.3f} m/s²"
                    f"  |  score: {e['motion_score']:.3f}"
                )
            else:
                lines.append(
                    f"  [t={e['timestamp']:5.0f}s]  {name:<22}|  a: {e['value']:.3f} m/s²"
                    f"  |  score: {e['motion_score']:.3f}"
                )

    return "\n".join(lines)



def print_flags(result):
    """Single-trip pretty printer. Still works as before."""
    
    print(f"  Trip: {result['trip_id']}")
    print(f"  Total events detected: {len(result['events'])}")

    if not result['events']:
        print("  No events detected.")
        return

    for e in sorted(result['events'], key=lambda x: x['timestamp']):
        name = LABEL_NAMES.get(e['label'], e['label'])
        if e['label'] == 'pothole':
            print(f"  [t={e['timestamp']:5.0f}s]  {name:<22}|  z: {e['value']:.3f} m/s²  |  score: {e['motion_score']:.3f}")
        else:
            print(f"  [t={e['timestamp']:5.0f}s]  {name:<22}|  a: {e['value']:.3f} m/s²  |  score: {e['motion_score']:.3f}")


def detect_motion_events(df):
    """
    Main entry point for motion analysis using the flagging system.
    
    This function accepts an accelerometer DataFrame and returns motion flags
    in the format expected by the analytics engine.
    
    Args:
        df: DataFrame with columns: trip_id, elapsed_seconds, accel_x, accel_y, 
            accel_z, speed_kmh, gps_lat, gps_lon
    
    Returns:
        DataFrame with columns: trip_id, timestamp, reason
    """
    result = process_all_trips(df)

    c = COLUMN_MAP
    has_abs_ts = 'timestamp' in df.columns
    has_elapsed = c['timestamp'] in df.columns

    trip_meta = {}
    if has_abs_ts and has_elapsed and TRIP_ID_COLUMN in df.columns:
        meta_cols = [TRIP_ID_COLUMN, c['timestamp'], 'timestamp']
        meta_df = df[meta_cols].copy()
        meta_df[c['timestamp']] = pd.to_numeric(meta_df[c['timestamp']], errors='coerce')

        for trip_id, grp in meta_df.groupby(TRIP_ID_COLUMN):
            g = grp.dropna(subset=[c['timestamp']]).copy()
            if g.empty:
                continue
            trip_meta[trip_id] = g

    def resolve_event_meta(trip_id, elapsed_seconds):
        grp = trip_meta.get(trip_id)
        if grp is None or grp.empty:
            return None

        idx = (grp[c['timestamp']] - float(elapsed_seconds)).abs().idxmin()
        row = grp.loc[idx]
        return row['timestamp']

    flags = []
    for event in result['all_events']:
        reason = LABEL_NAMES.get(event['label'], event['label'])
        elapsed_seconds = float(event['timestamp'])
        abs_timestamp = resolve_event_meta(event['trip_id'], elapsed_seconds)

        if abs_timestamp is None:
            event_timestamp = elapsed_seconds
        else:
            event_timestamp = abs_timestamp

        flags.append({
            'trip_id': event['trip_id'],
            'timestamp': event_timestamp,
            'reason': reason
        })
    
    return pd.DataFrame(flags)
