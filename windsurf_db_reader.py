#!/usr/bin/env python3
"""
Windsurf LevelDB Reader
A tool to read and explore Windsurf's local storage database.
"""

import os
import json
import sys
from pathlib import Path

try:
    import plyvel
except ImportError:
    print("plyvel not installed. Install with: pip install plyvel")
    sys.exit(1)

class WindsurfDBReader:
    def __init__(self, db_path=None):
        if db_path is None:
            # Default path for Windsurf Next on macOS
            home = Path.home()
            db_path = home / "Library/Application Support/Windsurf - Next/Local Storage/leveldb"
        
        self.db_path = Path(db_path)
        self.db = None
        
    def connect(self):
        """Connect to the LevelDB database"""
        try:
            self.db = plyvel.DB(str(self.db_path), create_if_missing=False)
            print(f"✅ Connected to database: {self.db_path}")
            return True
        except Exception as e:
            print(f"❌ Failed to connect to database: {e}")
            return False
    
    def close(self):
        """Close the database connection"""
        if self.db:
            self.db.close()
            print("🔒 Database connection closed")
    
    def list_all_keys(self, limit=50):
        """List all keys in the database"""
        if not self.db:
            print("❌ Database not connected")
            return
        
        print(f"\n📋 Listing up to {limit} keys:")
        count = 0
        for key, value in self.db:
            try:
                key_str = key.decode('utf-8', errors='ignore')
                value_preview = str(value[:100]) if len(value) > 100 else str(value)
                print(f"{count + 1:3d}. Key: {key_str}")
                print(f"     Value preview: {value_preview}")
                print(f"     Value size: {len(value)} bytes")
                print("-" * 50)
                
                count += 1
                if count >= limit:
                    break
            except Exception as e:
                print(f"Error reading key {count + 1}: {e}")
                count += 1
    
    def search_keys(self, pattern):
        """Search for keys containing a specific pattern"""
        if not self.db:
            print("❌ Database not connected")
            return
        
        print(f"\n🔍 Searching for keys containing '{pattern}':")
        found = 0
        for key, value in self.db:
            try:
                key_str = key.decode('utf-8', errors='ignore')
                if pattern.lower() in key_str.lower():
                    print(f"Found: {key_str}")
                    print(f"Value size: {len(value)} bytes")
                    
                    # Try to decode value if it looks like JSON
                    try:
                        if value.startswith(b'{') or value.startswith(b'['):
                            json_data = json.loads(value.decode('utf-8'))
                            print(f"JSON preview: {json.dumps(json_data, indent=2)[:200]}...")
                    except:
                        pass
                    
                    print("-" * 50)
                    found += 1
            except Exception as e:
                print(f"Error searching key: {e}")
        
        if found == 0:
            print(f"No keys found containing '{pattern}'")
    
    def get_value(self, key):
        """Get a specific value by key"""
        if not self.db:
            print("❌ Database not connected")
            return None
        
        try:
            key_bytes = key.encode('utf-8') if isinstance(key, str) else key
            value = self.db.get(key_bytes)
            
            if value is None:
                print(f"❌ Key '{key}' not found")
                return None
            
            print(f"✅ Found value for key '{key}':")
            print(f"Size: {len(value)} bytes")
            
            # Try to decode as JSON
            try:
                if value.startswith(b'{') or value.startswith(b'['):
                    json_data = json.loads(value.decode('utf-8'))
                    print("JSON content:")
                    print(json.dumps(json_data, indent=2))
                    return json_data
            except:
                pass
            
            # Try to decode as text
            try:
                text = value.decode('utf-8')
                print("Text content:")
                print(text)
                return text
            except:
                print("Binary content (showing first 200 bytes):")
                print(value[:200])
                return value
                
        except Exception as e:
            print(f"❌ Error getting value: {e}")
            return None
    
    def export_to_json(self, output_file="windsurf_db_export.json", max_entries=1000):
        """Export database contents to JSON file"""
        if not self.db:
            print("❌ Database not connected")
            return
        
        export_data = {}
        count = 0
        
        print(f"📤 Exporting database to {output_file}...")
        
        for key, value in self.db:
            if count >= max_entries:
                break
                
            try:
                key_str = key.decode('utf-8', errors='ignore')
                
                # Try to decode value as JSON first
                try:
                    if value.startswith(b'{') or value.startswith(b'['):
                        value_data = json.loads(value.decode('utf-8'))
                    else:
                        value_data = value.decode('utf-8', errors='ignore')
                except:
                    value_data = f"<binary data: {len(value)} bytes>"
                
                export_data[key_str] = value_data
                count += 1
                
            except Exception as e:
                print(f"Error exporting entry {count}: {e}")
        
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            print(f"✅ Exported {count} entries to {output_file}")
        except Exception as e:
            print(f"❌ Error writing export file: {e}")

def main():
    """Main function with interactive menu"""
    reader = WindsurfDBReader()
    
    if not reader.connect():
        return
    
    try:
        while True:
            print("\n" + "="*60)
            print("🌊 Windsurf Database Reader")
            print("="*60)
            print("1. List all keys (first 50)")
            print("2. Search keys by pattern")
            print("3. Get value by key")
            print("4. Export to JSON")
            print("5. Search for 'memory' related keys")
            print("6. Search for 'conversation' related keys")
            print("0. Exit")
            print("-"*60)
            
            choice = input("Enter your choice (0-6): ").strip()
            
            if choice == '0':
                break
            elif choice == '1':
                reader.list_all_keys()
            elif choice == '2':
                pattern = input("Enter search pattern: ").strip()
                if pattern:
                    reader.search_keys(pattern)
            elif choice == '3':
                key = input("Enter key: ").strip()
                if key:
                    reader.get_value(key)
            elif choice == '4':
                filename = input("Enter output filename (default: windsurf_db_export.json): ").strip()
                if not filename:
                    filename = "windsurf_db_export.json"
                reader.export_to_json(filename)
            elif choice == '5':
                reader.search_keys('memory')
            elif choice == '6':
                reader.search_keys('conversation')
            else:
                print("❌ Invalid choice. Please try again.")
                
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    finally:
        reader.close()

if __name__ == "__main__":
    main()
