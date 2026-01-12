#!/usr/bin/env python3
"""
Stash WebP Screenshot Remover Plugin
This plugin removes .webp scene screenshots and replaces them with .jpg alternatives.
"""

import json
import sys
import os
import requests
import base64
from typing import Optional, List, Dict, Any
from io import BytesIO

try:
    from PIL import Image
except ImportError:
    Image = None

class StashWebpRemover:
    def __init__(self):
        self.stash_url = os.environ.get('STASH_URL', 'http://localhost:9999')
        self.api_key = os.environ.get('STASH_API_KEY', '')
        self.graphql_url = f"{self.stash_url}/graphql"
        self.headers = {
            'Content-Type': 'application/json'
        }
        if self.api_key:
            self.headers['ApiKey'] = self.api_key
    
    def execute_query(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a GraphQL query against the Stash API."""
        payload = {
            'query': query,
        }
        if variables:
            payload['variables'] = variables
        
        try:
            response = requests.post(
                self.graphql_url,
                json=payload,
                headers=self.headers,
                timeout=30
            )
            
            data = response.json()
            
            if response.status_code != 200:
                print(f"HTTP Error {response.status_code}: {data}", file=sys.stderr)
                if 'errors' in data:
                    print(f"GraphQL Error: {data['errors']}", file=sys.stderr)
                return {}
            
            if 'errors' in data:
                print(f"GraphQL Error: {data['errors']}", file=sys.stderr)
                return {}
            
            return data.get('data', {})
        except requests.exceptions.RequestException as e:
            print(f"Request Error: {e}", file=sys.stderr)
            return {}
        except json.JSONDecodeError as e:
            print(f"JSON Decode Error: {e}", file=sys.stderr)
            return {}

    def execute_raw_query(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a GraphQL query and return the full JSON response (including errors).

        Returns a dict with keys: 'status_code' and 'response' (parsed JSON or raw text).
        """
        payload = {'query': query}
        if variables:
            payload['variables'] = variables

        try:
            response = requests.post(self.graphql_url, json=payload, headers=self.headers, timeout=30)
            try:
                data = response.json()
            except json.JSONDecodeError:
                data = {'raw': response.text}
            return {'status_code': response.status_code, 'response': data}
        except requests.exceptions.RequestException as e:
            return {'status_code': None, 'response': {'error': str(e)}}
    
    def get_all_scenes(self) -> List[Dict[str, Any]]:
        """Fetch all scenes from Stash."""
        query = """
        query {
            findScenes(filter: {per_page: -1}) {
                count
                scenes {
                    id
                    title
                    paths {
                        screenshot
                    }
                }
            }
        }
        """
        result = self.execute_query(query)
        return result.get('findScenes', {}).get('scenes', [])
    
    def get_stash_blobs_dir(self) -> Optional[str]:
        """Find and return the Stash blobs directory path."""
        stash_db_path = os.environ.get('STASH_DB_PATH')
        if stash_db_path:
            blobs = os.path.join(stash_db_path, 'blobs')
            if os.path.isdir(blobs):
                print(f"Using STASH_DB_PATH: {blobs}", file=sys.stderr)
                return blobs
        
        # Fallback: try common Stash installation locations
        possible_paths = [
            os.path.expanduser('~/.stash'),
            os.path.expanduser('~/AppData/Roaming/Stash'),  # Windows
            '/opt/stash'  # Linux
        ]
        
        for base_path in possible_paths:
            if os.path.exists(base_path):
                blobs = os.path.join(base_path, 'blobs')
                if os.path.isdir(blobs):
                    print(f"Found Stash at: {blobs}", file=sys.stderr)
                    return blobs
                else:
                    print(f"Checked {blobs} - not a directory", file=sys.stderr)
        
        print(f"Tried paths: {possible_paths}", file=sys.stderr)
        return None
    
    def find_webp_files(self) -> List[str]:
        """Find all .webp files in Stash blobs directory recursively. Returns list of full paths."""
        blobs_dir = self.get_stash_blobs_dir()
        if not blobs_dir:
            print("ERROR: Could not locate Stash blobs directory.", file=sys.stderr)
            return []
        
        # Normalize the path for the current OS
        blobs_dir = os.path.normpath(blobs_dir)
        
        print(f"Searching for WebP files in: {blobs_dir}", file=sys.stderr)
        print(f"Directory exists: {os.path.isdir(blobs_dir)}", file=sys.stderr)
        
        if not os.path.isdir(blobs_dir):
            print(f"ERROR: Directory does not exist or is not accessible!", file=sys.stderr)
            return []
        
        webp_files = []
        files_with_content = []
        
        try:
            # Stash stores blobs in subdirectories (hash-based), so we need to search recursively
            # Files don't have extensions, so we need to check file content
            for root, dirs, files in os.walk(blobs_dir):
                if files:
                    for filename in files:
                        full_path = os.path.join(root, filename)
                        files_with_content.append((root, filename, full_path))
                        
                        # Check if file starts with WebP magic bytes (RIFF...WEBP)
                        try:
                            with open(full_path, 'rb') as f:
                                header = f.read(12)
                                # WebP files start with RIFF and have WEBP at bytes 8-12
                                if header[:4] == b'RIFF' and header[8:12] == b'WEBP':
                                    webp_files.append(full_path)
                                    print(f"  Found WebP (by magic bytes): {root} / {filename}", file=sys.stderr)
                        except (IOError, OSError):
                            pass
        except (OSError, PermissionError) as e:
            print(f"ERROR reading blobs directory: {e}", file=sys.stderr)
        
        if not webp_files:
            print(f"No WebP files found. Scanned {len(files_with_content)} total files.", file=sys.stderr)
        else:
            print(f"Total WebP files found: {len(webp_files)}", file=sys.stderr)
        
        return webp_files
    
    def download_and_convert_webp(self, screenshot_url: str) -> Optional[bytes]:
        """
        Download image from Stash and convert to JPG if it's WebP.
        Returns the JPG image data as bytes, or None if not WebP or conversion fails.
        """
        if not Image:
            print("Pillow library not installed. Cannot convert images.", file=sys.stderr)
            return None
        
        try:
            # Download the image from the Stash URL, include Stash headers (ApiKey etc.)
            response = requests.get(screenshot_url, headers=self.headers, timeout=30)
            
            # If not HTTP 200, return None silently
            if response.status_code != 200:
                return None

            # Check content-type
            content_type = response.headers.get('Content-Type', '')
            if not content_type.startswith('image/'):
                return None

            # Try to open as image - if it fails, it's not an image format
            try:
                img = Image.open(BytesIO(response.content))
            except Exception:
                # Not a recognized image format
                return None
            
            # Check if it's WebP format
            if img.format != 'WEBP':
                # Not WebP, so we don't need to convert
                return None
            
            # Convert RGBA to RGB if necessary (JPG doesn't support transparency)
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Convert to JPG and save to bytes
            jpg_buffer = BytesIO()
            img.save(jpg_buffer, format='JPEG', quality=90)
            jpg_buffer.seek(0)
            
            return jpg_buffer.getvalue()
            
        except Exception as e:
            # Silently return None on any error
            return None
    
    def update_scene_screenshot(self, scene_id: str, image_data: bytes) -> bool:
        """Update a scene's screenshot with the provided image data (as bytes)."""
        query = """
        mutation UpdateScene($input: SceneUpdateInput!) {
            sceneUpdate(input: $input) {
                id
                title
                paths {
                    screenshot
                }
            }
        }
        """
        
        try:
            # Encode the image data as base64
            encoded_image = base64.b64encode(image_data).decode('utf-8')
            
            # Stash expects the cover image on the `cover_image` field as a data URI
            data_uri = f"data:image/jpeg;base64,{encoded_image}"
            variables = {
                'input': {
                    'id': scene_id,
                    'cover_image': data_uri
                }
            }

            raw = self.execute_raw_query(query, variables)
            status = raw.get('status_code')
            resp = raw.get('response', {})

            if status == 200 and isinstance(resp, dict) and 'data' in resp:
                data = resp.get('data', {})
                if 'sceneUpdate' in data and data['sceneUpdate']:
                    return True
                return False

            # Print debug info when validation fails
            print(f"HTTP Error {status}: {resp}", file=sys.stderr)
            return False
        except Exception as e:
            print(f"Error updating scene screenshot: {e}", file=sys.stderr)
            return False
    
    def process_scenes(self) -> Dict[str, Any]:
        """Main processing function to replace WebP screenshots."""
        stats = {
            'total_scenes': 0,
            'webp_screenshots_found': 0,
            'successfully_replaced': 0,
            'replacements': [],
            'errors': []
        }
        
        # First, find all WebP files in the filesystem to know what to look for
        print("Scanning for WebP files in Stash blobs directory...", file=sys.stderr)
        webp_files_in_fs = self.find_webp_files()
        
        if not webp_files_in_fs:
            print("No WebP files found. Nothing to convert.", file=sys.stderr)
            return stats
        
        print(f"Found {len(webp_files_in_fs)} WebP files to convert.", file=sys.stderr)
        
        # Create a set of base names (without extension) for quick lookup
        webp_basenames = set(os.path.basename(f)[:-5] for f in webp_files_in_fs)
        
        print("Fetching all scenes from Stash...", file=sys.stderr)
        scenes = self.get_all_scenes()
        
        if not scenes:
            print("No scenes found or error fetching scenes.", file=sys.stderr)
            stats['errors'].append('Failed to fetch scenes from Stash API')
            return stats
        
        stats['total_scenes'] = len(scenes)
        print(f"Processing {len(scenes)} scenes to find WebP screenshots...", file=sys.stderr)
        
        for scene in scenes:
            scene_id = scene.get('id')
            title = scene.get('title', 'Unknown')
            screenshot_path = scene.get('paths', {}).get('screenshot')
            
            # Check if screenshot exists
            if screenshot_path and 'screenshot' in screenshot_path:
                # Try to download and convert - only succeeds if it's actually WebP
                image_data = self.download_and_convert_webp(screenshot_path)
                
                if image_data is not None:
                    # It was WebP and we successfully converted it
                    stats['webp_screenshots_found'] += 1
                    print(f"Converted WebP to JPG for scene: {title}", file=sys.stderr)
                    success = self.update_scene_screenshot(scene_id, image_data)
                    
                    if success:
                        stats['successfully_replaced'] += 1
                        stats['replacements'].append({
                            'scene_id': scene_id,
                            'title': title,
                            'original_url': screenshot_path,
                            'action': 'converted_webp_to_jpg'
                        })
                        print(f"✓ Updated: {title}", file=sys.stderr)
                    else:
                        error_msg = f"Failed to update scene {scene_id} ({title})"
                        stats['errors'].append(error_msg)
                        print(f"✗ {error_msg}", file=sys.stderr)
        
        return stats
    
    def run(self):
        """Execute the plugin."""
        try:
            stats = self.process_scenes()
            
            # Output results as JSON
            output = {
                'success': True,
                'stats': stats
            }
            
            print(json.dumps(output, indent=2))
            
        except Exception as e:
            error_output = {
                'success': False,
                'error': str(e)
            }
            print(json.dumps(error_output, indent=2))
            sys.exit(1)


if __name__ == '__main__':
    remover = StashWebpRemover()
    remover.run()
