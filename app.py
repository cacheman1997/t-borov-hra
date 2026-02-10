import os
import json
import time
from flask import Flask, render_template, request, send_from_directory, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.utils import secure_filename

app = Flask(__name__, static_folder='.', static_url_path='')
app.config['SECRET_KEY'] = 'secret_key_camp_game'
app.config['UPLOAD_FOLDER'] = 'uploads'

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

socketio = SocketIO(app, cors_allowed_origins="*")

# In-memory storage (replace with DB for persistence)
# territories: { "1": { "owner": "red", "capturedAt": timestamp } }
territories = {}
# active_requests: { "req_id": { type: "check_location", team: "red", lat: ..., lng: ..., territoryId: "1", status: "pending" } }
active_requests = {}
# teams: { "red": { "socketId": "..." } }
teams = {}
# team_scores: { "red": 1234.5 }
team_scores = {}

# Passwords
TEAM_PASSWORDS = {
    "cerveni":  "58vrlW43",
    "modri":  "fXtKZeEs",
    "zeleni":  "qOCQTcxR",
    "zluti":  "ZTBny5Ho",
    "oranzovi":  "Hly3pIc4",
    "fialovi":  "PCKYa5Fl",
    "bilí":  "BLVXM9t6",
    "admin":  "CpUu9KSh"
}

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('.', path)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if file:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        return jsonify({'filename': filename}), 200

# Socket Events

@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('login_request')
def handle_login_request(data):
    # data: { teamId, password }
    team = data.get('teamId')
    pwd = data.get('password')
    
    if team in TEAM_PASSWORDS and TEAM_PASSWORDS[team] == pwd:
        emit('login_response', {'success': True, 'teamId': team, 'role': 'admin' if team == 'admin' else 'team'})
    else:
        emit('login_response', {'success': False, 'message': 'Špatné heslo'})

@socketio.on('join_game')
def handle_join(data):
    # data: { role: 'admin' | 'team', teamId: 'red' }
    role = data.get('role')
    team_id = data.get('teamId')
    
    join_room(role) # 'admin' room or 'team' room (generic)
    
    if role == 'team' and team_id:
        join_room(f"team_{team_id}")
        teams[team_id] = request.sid
        emit('map_update', territories, to=request.sid) # Send current map state
        emit('init_scores', team_scores, to=request.sid) # Send scores
        
        # Check for active request for this team
        existing_req = None
        for rid, req in active_requests.items():
            if req.get('teamId') == team_id:
                existing_req = req
                break
        
        if existing_req:
            emit('restore_request', existing_req, to=request.sid)

        print(f"Team {team_id} joined")
    elif role == 'admin':
        join_room('admin')
        # Send current state to admin
        emit('init_state', {'territories': territories, 'requests': active_requests, 'scores': team_scores}, to=request.sid)
        print("Admin joined")

@socketio.on('request_location_check')
def handle_location_check(data):
    # data: { teamId, lat, lng, territoryId }
    raw_tid = data.get('territoryId')
    territory_id = str(raw_tid) if raw_tid is not None else None
    
    print(f"DEBUG: request_location_check for territory '{territory_id}' (type: {type(raw_tid)})")

    # Check if territory is locked
    if territory_id in territories:
        t = territories[territory_id]
        if 'lockedUntil' in t:
            remaining = t['lockedUntil'] - time.time()
            if remaining > 0:
                print(f"DEBUG: Territory {territory_id} is locked for {remaining}s")
                emit('error_message', {'message': f'Území {territory_id} je uzamčeno ještě {int(remaining/60)} minut!'}, to=request.sid)
                return
            else:
                 # Lock expired, cleanup optional but good practice
                 print(f"DEBUG: Lock expired for {territory_id}")

    # Check if team already has an active request
    for req in active_requests.values():
        if req.get('teamId') == data.get('teamId'):
            emit('error_message', {'message': 'Máte již aktivní žádost! Musíte ji nejprve zrušit.'}, to=request.sid)
            return

    req_id = os.urandom(4).hex()
    new_req = {
        'id': req_id,
        'type': 'location_check',
        'status': 'pending',
        **data,
        'territoryId': territory_id, # Ensure stored as string
        'timestamp': time.time()
    }
    active_requests[req_id] = new_req
    # Notify Admin
    emit('new_request', new_req, to='admin')

@socketio.on('admin_verify_location')
def handle_admin_verify(data):
    # data: { reqId, approved: boolean, taskText: string (if approved) }
    req_id = data.get('reqId')
    approved = data.get('approved')
    task_text = data.get('taskText', '')
    
    if req_id in active_requests:
        req = active_requests[req_id]
        req['status'] = 'approved' if approved else 'rejected'
        
        # Notify Team
        team_room = f"team_{req['teamId']}"
        emit('location_verification_result', {
            'reqId': req_id,
            'approved': approved,
            'taskText': task_text,
            'territoryId': req['territoryId']
        }, to=team_room)
        
        # If rejected, remove request
        if not approved:
            del active_requests[req_id]
            emit('request_removed', {'reqId': req_id}, to='admin')
        else:
            # Update request to wait for task response
            req['type'] = 'task_response_pending'
            req['taskText'] = task_text
            # Notify all admins of update
            emit('request_updated', req, to='admin')

@socketio.on('submit_task_response')
def handle_task_response(data):
    # data: { reqId, responseType: 'text'|'image', content: 'text'|'filename' }
    req_id = data.get('reqId')
    if req_id in active_requests:
        req = active_requests[req_id]
        req['response'] = data
        req['status'] = 'review_pending'
        
        # Notify Admin
        emit('task_response_received', req, to='admin')

@socketio.on('admin_verify_task')
def handle_admin_verify_task(data):
    global team_scores # Explicitly declare global to avoid NameError if scope confusion exists
    try:
        # data: { reqId, approved: boolean }
        print(f"DEBUG: admin_verify_task received: {data}")
        req_id = data.get('reqId')
        approved = data.get('approved')
        
        # Ensure approved is strictly boolean True (handle potential string "true" if needed, though socketio handles JSON types)
        if isinstance(approved, str):
            approved = approved.lower() == 'true'
        
        if req_id in active_requests:
            req = active_requests[req_id]
            team_room = f"team_{req['teamId']}"
            
            if approved:
                # Update Territory
                territory_id = str(req['territoryId']) # Ensure string
                # Lock for 30 minutes
                lock_duration = 30 * 60 
                
                print(f"DEBUG: Territory {territory_id} captured by {req['teamId']}, locking until {time.time() + lock_duration}")

                # Update scores for the previous owner
                now = time.time()
                if territory_id in territories:
                    prev_t = territories[territory_id]
                    prev_owner = prev_t.get('owner')
                    prev_captured_at = prev_t.get('capturedAt')
                    
                    if prev_owner and prev_captured_at:
                        # Ensure prev_captured_at is a number
                        try:
                            prev_captured_at = float(prev_captured_at)
                            duration = now - prev_captured_at
                            if prev_owner not in team_scores:
                                team_scores[prev_owner] = 0
                            team_scores[prev_owner] += duration
                            print(f"DEBUG: Added {duration}s to {prev_owner}. Total: {team_scores[prev_owner]}")
                        except Exception as e:
                            print(f"ERROR calculating score: {e}")

                territories[territory_id] = {
                    'owner': req['teamId'],
                    'capturedAt': now,
                    'lockedUntil': now + lock_duration
                }
                emit('territory_captured', {
                    'territoryId': territory_id,
                    'owner': req['teamId']
                }, to='admin') # Broadcast to everyone? Maybe just admin and the team?
                emit('territory_update', territories[territory_id], to=team_room) # Notify winner
                socketio.emit('game_state_update', {'territories': territories, 'scores': team_scores}) # Notify everyone
                
                # --- NEW: Cancel other requests for this territory ---
                reqs_to_remove = []
                for other_rid, other_req in active_requests.items():
                    if other_rid != req_id and str(other_req.get('territoryId')) == territory_id:
                        reqs_to_remove.append(other_rid)
                        # Notify the other team
                        other_team_room = f"team_{other_req['teamId']}"
                        emit('error_message', {'message': f'Území {territory_id} bylo právě zabráno jiným týmem! Vaše žádost byla zrušena.'}, to=other_team_room)
                        # Force reset their UI
                        emit('request_cancelled_confirmation', {}, to=other_team_room)

                for rid in reqs_to_remove:
                    if rid in active_requests:
                        del active_requests[rid]
                        emit('request_removed', {'reqId': rid}, to='admin')
                # -----------------------------------------------------

            emit('task_result', {'approved': approved, 'territoryId': req['territoryId']}, to=team_room)
            
            # Cleanup request
            del active_requests[req_id]
            emit('request_removed', {'reqId': req_id}, to='admin')
        else:
            print(f"DEBUG: Request {req_id} not found in active_requests")
            
    except Exception as e:
        import traceback
        print(f"ERROR in handle_admin_verify_task: {e}")
        traceback.print_exc()
        emit('error_message', {'message': 'Chyba serveru při schvalování úkolu'}, to=request.sid)

# Ensure team_scores is available globally if accessed within function scope but defined outside
# Python usually handles this fine for read/mutate, but if there was confusion, this comment confirms structure.
# Global vars: territories, active_requests, teams, team_scores

@socketio.on('request_map_update')
def handle_map_update_request():
    emit('map_update', territories, to=request.sid)

@socketio.on('admin_clear_all_requests')
def handle_admin_clear_requests():
    global active_requests
    print("DEBUG: Admin requested clearing all requests")
    active_requests.clear()
    emit('requests_cleared', {}, to='admin')

@socketio.on('cancel_request')
def handle_cancel_request(data):
    # data: { teamId }
    team_id = data.get('teamId')
    print(f"DEBUG: Cancel request for team {team_id}")
    
    req_to_remove = None
    
    # Find request by team_id
    for rid, req in active_requests.items():
        if req.get('teamId') == team_id:
            req_to_remove = rid
            break
            
    if req_to_remove:
        del active_requests[req_to_remove]
        emit('request_removed', {'reqId': req_to_remove}, to='admin')
        emit('request_cancelled_confirmation', {}, to=request.sid)
        print(f"DEBUG: Request {req_to_remove} cancelled by user")
    else:
        # Even if not found (maybe already gone), tell client it's done
        emit('request_cancelled_confirmation', {}, to=request.sid)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    socketio.run(app, debug=debug, host='0.0.0.0', port=port)
