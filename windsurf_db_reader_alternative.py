#!/usr/bin/env python3
"""
Windsurf LevelDB Reader - Alternative Implementation
A tool to read and explore Windsurf's local storage database using pure Python.
"""

import os
import json
import sys
import struct
from pathlib import Path

class SimpleLevelDBReader:
    """
    A simple LevelDB reader that can extract basic data without full LevelDB library.
    This is a simplified approach that may not work for all LevelDB files but can
    extract readable data from many cases.
    """
    
    def __init__(self, db_path=None):
        if db_path is None:
            # Default path for Windsurf Next on macOS
            home = Path.home()
            db_path = home / "Library/Application Support/Windsurf - Next/Local Storage/leveldb"
        
        self.db_path = Path(db_path)
        
    def read_ldb_files(self):
        """Read .ldb files and try to extract readable data"""
        if not self.db_path.exists():
            print(f"❌ Database path does not exist: {self.db_path}")
            return []
        
        ldb_files = list(self.db_path.glob("*.ldb"))
        if not ldb_files:
            print("❌ No .ldb files found")
            return []
        
        print(f"📁 Found {len(ldb_files)} .ldb files")
        
        all_data = []
        for ldb_file in ldb_files:
            print(f"📖 Reading {ldb_file.name}...")
            data = self._extract_strings_from_ldb(ldb_file)
            all_data.extend(data)
        
        return all_data
    
    def _extract_strings_from_ldb(self, file_path):
        """Extract readable strings from an LDB file"""
        extracted_data = []
        
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
                
            # Look for JSON-like structures and readable strings
            current_string = ""
            in_string = False
            
            for i, byte in enumerate(content):
                char = chr(byte) if 32 <= byte <= 126 else None  # Printable ASCII
                
                if char:
                    current_string += char
                    in_string = True
                else:
                    if in_string and len(current_string) > 10:  # Only keep longer strings
                        # Check if it looks like JSON or contains useful data
                        if (current_string.startswith('{') or 
                            current_string.startswith('[') or
                            'memory' in current_string.lower() or
                            'conversation' in current_string.lower() or
                            'windsurf' in current_string.lower()):
                            extracted_data.append({
                                'file': file_path.name,
                                'offset': i - len(current_string),
                                'content': current_string,
                                'type': self._guess_content_type(current_string)
                            })
                    current_string = ""
                    in_string = False
            
            # Don't forget the last string
            if in_string and len(current_string) > 10:
                extracted_data.append({
                    'file': file_path.name,
                    'offset': len(content) - len(current_string),
                    'content': current_string,
                    'type': self._guess_content_type(current_string)
                })
                
        except Exception as e:
            print(f"❌ Error reading {file_path}: {e}")
        
        return extracted_data
    
    def _guess_content_type(self, content):
        """Guess the type of content"""
        content_lower = content.lower()
        
        if content.startswith('{') and content.endswith('}'):
            return 'json_object'
        elif content.startswith('[') and content.endswith(']'):
            return 'json_array'
        elif 'memory' in content_lower:
            return 'memory_related'
        elif 'conversation' in content_lower:
            return 'conversation_related'
        elif any(keyword in content_lower for keyword in ['windsurf', 'cascade', 'user', 'assistant']):
            return 'windsurf_related'
        else:
            return 'text'
    
    def search_data(self, data, pattern):
        """Search extracted data for a pattern"""
        results = []
        pattern_lower = pattern.lower()
        
        for item in data:
            if pattern_lower in item['content'].lower():
                results.append(item)
        
        return results
    
    def export_data(self, data, output_file="windsurf_extracted_data.json"):
        """Export extracted data to JSON"""
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"✅ Exported {len(data)} items to {output_file}")
        except Exception as e:
            print(f"❌ Error exporting data: {e}")
    
    def analyze_data(self, data):
        """Analyze the extracted data"""
        if not data:
            print("❌ No data to analyze")
            return
        
        print(f"\n📊 Analysis of {len(data)} extracted items:")
        print("-" * 50)
        
        # Count by type
        type_counts = {}
        for item in data:
            item_type = item['type']
            type_counts[item_type] = type_counts.get(item_type, 0) + 1
        
        print("📈 Content types:")
        for content_type, count in sorted(type_counts.items()):
            print(f"  {content_type}: {count}")
        
        # Count by file
        file_counts = {}
        for item in data:
            file_name = item['file']
            file_counts[file_name] = file_counts.get(file_name, 0) + 1
        
        print(f"\n📁 Items per file:")
        for file_name, count in sorted(file_counts.items()):
            print(f"  {file_name}: {count}")
        
        # Show some examples
        print(f"\n🔍 Sample content:")
        for i, item in enumerate(data[:5]):  # Show first 5 items
            content_preview = item['content'][:100] + "..." if len(item['content']) > 100 else item['content']
            print(f"  {i+1}. [{item['type']}] {content_preview}")

def main():
    """Main function with interactive menu"""
    reader = SimpleLevelDBReader()
    
    print("🌊 Windsurf Database Reader (Alternative)")
    print("=" * 60)
    print("This tool extracts readable strings from LevelDB files.")
    print("It may not capture all data but can find JSON and text content.")
    print("=" * 60)
    
    try:
        while True:
            print("\nOptions:")
            print("1. Extract all readable data")
            print("2. Search for specific pattern")
            print("3. Analyze extracted data")
            print("4. Export data to JSON")
            print("0. Exit")
            print("-" * 40)
            
            choice = input("Enter your choice (0-4): ").strip()
            
            if choice == '0':
                break
            elif choice == '1':
                print("🔄 Extracting data from LevelDB files...")
                data = reader.read_ldb_files()
                if data:
                    reader.analyze_data(data)
                    # Store data for other operations
                    globals()['extracted_data'] = data
                else:
                    print("❌ No readable data found")
            elif choice == '2':
                if 'extracted_data' not in globals():
                    print("❌ Please extract data first (option 1)")
                    continue
                pattern = input("Enter search pattern: ").strip()
                if pattern:
                    results = reader.search_data(globals()['extracted_data'], pattern)
                    print(f"\n🔍 Found {len(results)} matches for '{pattern}':")
                    for i, item in enumerate(results[:10]):  # Show first 10 matches
                        content_preview = item['content'][:200] + "..." if len(item['content']) > 200 else item['content']
                        print(f"\n{i+1}. File: {item['file']}, Type: {item['type']}")
                        print(f"Content: {content_preview}")
                        print("-" * 40)
            elif choice == '3':
                if 'extracted_data' not in globals():
                    print("❌ Please extract data first (option 1)")
                    continue
                reader.analyze_data(globals()['extracted_data'])
            elif choice == '4':
                if 'extracted_data' not in globals():
                    print("❌ Please extract data first (option 1)")
                    continue
                filename = input("Enter output filename (default: windsurf_extracted_data.json): ").strip()
                if not filename:
                    filename = "windsurf_extracted_data.json"
                reader.export_data(globals()['extracted_data'], filename)
            else:
                print("❌ Invalid choice. Please try again.")
                
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")

if __name__ == "__main__":
    main()
