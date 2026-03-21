import os
import re

def find_commands(directory="cogs"):
    commands_list = []
    
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                print(f"Checking: {filepath}")
                
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                    app_commands = re.findall(r'@app_commands\.command\([^)]*name="([^"]+)"', content)
                    hybrid_commands = re.findall(r'@commands\.hybrid_command\([^)]*name="([^"]+)"', content)
                    prefix_commands = re.findall(r'@commands\.command\([^)]*name="([^"]+)"', content)
                    
                    for cmd in app_commands:
                        commands_list.append(f"[SLASH] {file}: {cmd}")
                    for cmd in hybrid_commands:
                        commands_list.append(f"[HYBRID] {file}: {cmd}")
                    for cmd in prefix_commands:
                        commands_list.append(f"[PREFIX] {file}: {cmd}")
    
    return commands_list

if __name__ == "__main__":
    print("="*50)
    print("SEARCHING FOR COMMANDS")
    print("="*50)
    print()
    
    commands = find_commands()
    
    if commands:
        print("\n" + "="*50)
        print("FOUND COMMANDS:")
        print("="*50)
        for cmd in commands:
            print(cmd)
        print(f"\nTotal: {len(commands)} commands")
    else:
        print("No commands found. Check if 'cogs' folder exists.")