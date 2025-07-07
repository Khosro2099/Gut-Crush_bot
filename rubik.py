
import pyrubi
import json
import os
import re
import threading
import time
from typing import List, Dict, Set, Optional

# Global variables
bots = {
    'bot1': pyrubi.Client('bot1'),
    'bot2': pyrubi.Client('bot2')
}
FILE_NAME = "messages.json"
all_members = []  # All available members
sent_members = set()  # Members who received messages
stop_sending = False
joined_groups = set()  # Groups we already joined

# Initialize bots and load members
def initialize_bots():
    """Load members from all groups and channels"""
    global all_members
    
    for bot_name, bot in bots.items():
        groups = []
        data = bot.get_chats()
        for chat in data['chats']:
            if chat['abs_object']['type'] in ['Group', 'Channel']:
                groups.append(chat['object_guid'])

        for group in groups:
            try:
                mems = bot.get_all_members(group)
                for member in mems.get('in_chat_members', []):
                    if member['member_guid'] not in all_members:
                        all_members.append(member['member_guid'])
            except Exception as e:
                print(f"Error in {bot_name}: {str(e)}")

# Initialize the bots
initialize_bots()

# Helper functions
def extract_group_links(text: str) -> List[str]:
    """Extract Rubika group links from text"""
    pattern = r'https://rubika\.ir/joing/[a-zA-Z0-9+]{20,}'
    return re.findall(pattern, text)

def get_member_limit(total_members: int) -> int:
    """Get how many members should receive messages"""
    while True:
        try:
            limit = int(input(f"\nEnter number of members to send (max {total_members}): "))
            if 1 <= limit <= total_members:
                return limit
            print(f"Please enter between 1 and {total_members}")
        except ValueError:
            print("Please enter a valid number!")

def validate_file_path(file_path: str) -> bool:
    """Check if file exists and is accessible"""
    if not os.path.exists(file_path):
        print("Error: File does not exist!")
        return False
    if not os.path.isfile(file_path):
        print("Error: Path is not a file!")
        return False
    return True

# Account management
def list_acc():
    """List all available accounts"""
    print("\nAvailable accounts:")
    for i, (bot_name, bot) in enumerate(bots.items(), 1):
        print(f"{i}. {bot_name} ({bot.sessionData['user']['first_name']})")

def select_accounts() -> List[pyrubi.Client]:
    """Let user select which accounts to use"""
    list_acc()
    print("\nSelect accounts (comma separated):")
    print("Example: 1,3 for first and third")
    print("Enter 'all' for all accounts")
    
    choices = input("Your choice: ").strip().lower()
    
    if choices == 'all':
        return list(bots.values())
    
    selected = []
    for choice in choices.split(','):
        try:
            index = int(choice.strip()) - 1
            if 0 <= index < len(bots):
                selected.append(list(bots.values())[index])
        except (ValueError, IndexError):
            pass
    
    return selected if selected else list(bots.values())

# Message management
def load_messages() -> List[str]:
    """Load saved messages"""
    if not os.path.exists(FILE_NAME):
        return []
    
    with open(FILE_NAME, 'r', encoding='utf-8') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []

def save_messages(messages: List[str]):
    """Save messages to file"""
    with open(FILE_NAME, 'w', encoding='utf-8') as f:
        json.dump(messages, f, ensure_ascii=False, indent=2)

def addmsg():
    """Add new message"""
    text = input('Enter your message: \n')
    messages = load_messages()
    messages.append(text)
    save_messages(messages)
    print(f"Message saved: {text[:30]}...")

def select_message() -> Optional[str]:
    """Select message from saved ones"""
    messages = load_messages()
    if not messages:
        print("No saved messages!")
        return None
    
    print("\nSaved messages:")
    for i, msg in enumerate(messages, 1):
        print(f"{i}. {msg[:50]}{'...' if len(msg) > 50 else ''}")
    
    try:
        choice = int(input("\nSelect message number: ")) - 1
        if 0 <= choice < len(messages):
            return messages[choice]
        print("Invalid selection!")
    except ValueError:
        print("Please enter a number!")
    return None

# Sending system
def wait_for_stop_command():
    """Wait for stop command from user"""
    global stop_sending
    while not stop_sending:
        if input() == 's':
            stop_sending = True
            break

def send_to_members(selected_bots: List[pyrubi.Client], content_func, content_args=None, content_type="text"):
    """Main sending function with all features"""
    global stop_sending, sent_members
    
    available_members = [m for m in all_members if m not in sent_members]
    if not available_members:
        print("\nAll members received messages!")
        return
    
    limit = get_member_limit(len(available_members))
    stop_sending = False
    sent_count = 0
    
    print(f"\nPress 's'+Enter to stop sending")
    stop_thread = threading.Thread(target=wait_for_stop_command)
    stop_thread.daemon = True
    stop_thread.start()
    
    for bot in selected_bots:
        if stop_sending or sent_count >= limit:
            break
            
        bot_name = list(bots.keys())[list(bots.values()).index(bot)]
        print(f"\nSending with {bot_name}...")
        
        for member in available_members:
            if stop_sending or sent_count >= limit:
                break
                
            if member in sent_members:
                continue
                
            try:
                if content_type == "text":
                    bot.send_text(member, content_func)
                elif content_type == "image":
                    bot.send_image(member, content_func, text=content_args)
                elif content_type == "video":
                    bot.send_video(member, content_func, text=content_args)
                elif content_type == "music":
                    bot.send_music(member, content_func, text=content_args)
                elif content_type == "file":
                    bot.send_file(member, content_func, text=content_args)
                
                sent_members.add(member)
                sent_count += 1
                print(f"Sent to {sent_count}/{limit}", end='\r')
            except Exception as e:
                print(f"\nError sending: {str(e)}")
    
    stop_sending = False
    print(f"\nDone: Sent to {sent_count} members")
    print(f"Total received: {len(sent_members)}/{len(all_members)}")

# Content sending
def send_msg(selected_bots: List[pyrubi.Client], text: str):
    """Send text message"""
    send_to_members(selected_bots, text, None, "text")

def send_pic(selected_bots: List[pyrubi.Client]):
    """Send photo with caption - path input"""
    while True:
        file_path = input("\nEnter image file path (or '0' to cancel): ").strip()
        if file_path == '0':
            return
        
        if validate_file_path(file_path):
            caption = input('Enter caption (leave empty for no caption): ')
            send_to_members(selected_bots, file_path, caption, "image")
            return

def send_vid(selected_bots: List[pyrubi.Client]):
    """Send video with caption - path input"""
    while True:
        file_path = input("\nEnter video file path (or '0' to cancel): ").strip()
        if file_path == '0':
            return
        
        if validate_file_path(file_path):
            caption = input('Enter caption (leave empty for no caption): ')
            send_to_members(selected_bots, file_path, caption, "video")
            return

def send_music(selected_bots: List[pyrubi.Client]):
    """Send music with caption - path input"""
    while True:
        file_path = input("\nEnter audio file path (or '0' to cancel): ").strip()
        if file_path == '0':
            return
        
        if validate_file_path(file_path):
            caption = input('Enter caption (leave empty for no caption): ')
            send_to_members(selected_bots, file_path, caption, "music")
            return

def send_file(selected_bots: List[pyrubi.Client]):
    """Send file with caption - path input"""
    while True:
        file_path = input("\nEnter file path (or '0' to cancel): ").strip()
        if file_path == '0':
            return
        
        if validate_file_path(file_path):
            caption = input('Enter caption (leave empty for no caption): ')
            send_to_members(selected_bots, file_path, caption, "file")
            return

# Group finder system
def find_and_join_groups(selected_bots: List[pyrubi.Client], max_groups: int = 10):
    """Find and join groups from channels"""
    global joined_groups
    
    for bot in selected_bots:
        bot_name = list(bots.keys())[list(bots.values()).index(bot)]
        print(f"\nFinding groups with {bot_name}...")
        
        channels = []
        data = bot.get_chats()
        for chat in data['chats']:
            if chat['abs_object']['type'] == 'Channel':
                channels.append(chat['object_guid'])
        
        print(f"Found {len(channels)} channels")
        
        joined_count = 0
        for channel in channels[:5]:  # Check max 5 channels
            if joined_count >= max_groups:
                break
                
            try:
                messages = bot.get_messages(channel)
                message_batch = messages.get('messages', [])[:50]  # Check first 50 msgs
                print(f"\nChecking channel {channel}")
                
                for msg in message_batch:
                    if joined_count >= max_groups:
                        break
                        
                    if 'text' in msg:
                        links = extract_group_links(msg['text'])
                        for link in links:
                            if link in joined_groups:
                                continue
                                
                            try:
                                print(f"\nFound group link: {link}")
                                result = bot.join_chat(link)
                                if result.get('status') == 'OK':
                                    print(f"Joined successfully!")
                                    joined_groups.add(link)
                                    joined_count += 1
                                    time.sleep(5)  # Rate limit
                                else:
                                    print("Failed to join")
                            except Exception as e:
                                print(f"Error: {str(e)}")
            
            except Exception as e:
                print(f"Error in channel {channel}: {str(e)}")
        
        print(f"\nJoined {joined_count} new groups")

# Menu system
def msg_menu():
    """Message management menu"""
    while True:
        print("\n--- Message Management ---")
        print("1. Add new message")
        print("2. Show saved messages")
        print("0. Back to main menu")
        
        choice = input("Your choice: ")
        
        if choice == "1":
            addmsg()
        elif choice == "2":
            messages = load_messages()
            if messages:
                print("\nSaved messages:")
                for i, msg in enumerate(messages, 1):
                    print(f"{i}. {msg[:50]}{'...' if len(msg) > 50 else ''}")
            else:
                print("No saved messages.")
        elif choice == "0":
            break
        else:
            print("Invalid choice!")

def reset_sent_members():
    """Reset sent members list"""
    global sent_members
    sent_members = set()
    print("\nReset done - All members can receive again")

def main_menu():
    """Main menu"""
    while True:
        print("\n--- Main Menu ---")
        print("1. Show accounts")
        print("2. Message management")
        print("3. Send text")
        print("4. Send photo")
        print("5. Send video")
        print("6. Send music")
        print("7. Send file")
        print("8. Reset sent list")
        print("9. Find and join groups")
        print("0. Exit")
        
        choice = input("Your choice: ")
        
        if choice == "1":
            list_acc()
        elif choice == "2":
            msg_menu()
        elif choice == "3":
            selected = select_accounts()
            print("\nMessage source:")
            print("1. New message")
            print("2. From saved")
            msg_choice = input("Your choice: ")
            
            if msg_choice == "1":
                text = input("Enter text: ")
                send_msg(selected, text)
            elif msg_choice == "2":
                text = select_message()
                if text:
                    send_msg(selected, text)
            else:
                print("Invalid choice!")
        elif choice == "4":
            selected = select_accounts()
            send_pic(selected)
        elif choice == "5":
            selected = select_accounts()
            send_vid(selected)
        elif choice == "6":
            selected = select_accounts()
            send_music(selected)
        elif choice == "7":
            selected = select_accounts()
            send_file(selected)
        elif choice == "8":
            reset_sent_members()
        elif choice == "9":
            selected = select_accounts()
            try:
                max_groups = int(input("Max groups to join (default 10): ") or "10")
                find_and_join_groups(selected, max_groups)
            except ValueError:
                print("Enter a valid number!")
        elif choice == "0":
            print("Exiting...")
            break
        else:
            print("Invalid choice!")

if __name__ == "__main__":
    main_menu()
