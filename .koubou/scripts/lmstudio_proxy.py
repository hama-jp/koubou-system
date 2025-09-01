#!/usr/bin/env python3
"""
LMStudio API Proxy for Codex CLI
Converts array input to string for embeddings API compatibility
"""

from flask import Flask, request, jsonify, Response
import requests
import json

app = Flask(__name__)

LMSTUDIO_BASE_URL = "http://192.168.11.29:1234"

@app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
def proxy(path):
    """Proxy all requests to LMStudio, converting formats as needed"""
    
    target_url = f"{LMSTUDIO_BASE_URL}/{path}"
    
    # Get request data
    data = None
    if request.method in ['POST', 'PUT', 'PATCH']:
        try:
            data = request.get_json()
            
            # Convert array input to string for embeddings endpoint
            if 'embeddings' in path and data and 'input' in data:
                if isinstance(data['input'], list) and len(data['input']) > 0:
                    # Convert first element of array to string
                    data['input'] = data['input'][0] if isinstance(data['input'][0], str) else str(data['input'][0])
                    print(f"Converted input from array to string: {data['input'][:50]}...")
            
            # Log the request for debugging
            print(f"{request.method} {path}")
            print(f"Request data: {json.dumps(data, indent=2)[:500]}")
            
        except Exception as e:
            print(f"Error processing request data: {e}")
            data = request.get_data()
    
    # Forward request to LMStudio
    try:
        response = requests.request(
            method=request.method,
            url=target_url,
            headers={key: value for key, value in request.headers if key != 'Host'},
            json=data if isinstance(data, dict) else None,
            data=data if not isinstance(data, dict) else None,
            params=request.args,
            stream=True
        )
        
        # Stream response back
        def generate():
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    yield chunk
        
        return Response(
            generate(),
            status=response.status_code,
            headers=dict(response.headers)
        )
        
    except Exception as e:
        print(f"Error proxying request: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print("Starting LMStudio Proxy on http://localhost:8889")
    print(f"Forwarding to {LMSTUDIO_BASE_URL}")
    app.run(host='0.0.0.0', port=8889, debug=False)