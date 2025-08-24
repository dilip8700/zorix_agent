#!/usr/bin/env python3
"""
Direct Chat with Zorix Agent AI

This script lets you chat directly with the AI model.
"""

import os
import sys
import json
import asyncio
from pathlib import Path

# Add the agent directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

async def test_bedrock_connection():
    """Test if AWS Bedrock is working."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
        
        import boto3
        from botocore.exceptions import ClientError
        
        # Test connection
        client = boto3.client('bedrock-runtime', region_name='us-east-1')
        
        # Try a simple request
        response = client.invoke_model(
            modelId='anthropic.claude-3-5-sonnet-20240620-v1:0',
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 100,
                "messages": [
                    {"role": "user", "content": "Hello, can you respond with just 'AI is working!'?"}
                ]
            })
        )
        
        result = json.loads(response['body'].read())
        print("✅ AWS Bedrock is working!")
        print(f"🤖 AI Response: {result['content'][0]['text']}")
        return True
        
    except Exception as e:
        print(f"❌ AWS Bedrock error: {e}")
        return False

async def chat_with_ai():
    """Interactive chat with AI."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
        
        import boto3
        import json
        
        client = boto3.client('bedrock-runtime', region_name='us-east-1')
        
        print("🤖 Zorix Agent AI Chat")
        print("=" * 40)
        print("Type 'quit' to exit")
        print("Type 'help' for commands")
        print()
        
        while True:
            user_input = input("You: ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("👋 Goodbye!")
                break
            
            if user_input.lower() == 'help':
                print("Commands:")
                print("  help - Show this help")
                print("  quit - Exit chat")
                print("  clear - Clear screen")
                continue
            
            if user_input.lower() == 'clear':
                os.system('cls' if os.name == 'nt' else 'clear')
                continue
            
            if not user_input:
                continue
            
            print("🤖 AI: ", end="", flush=True)
            
            try:
                response = client.invoke_model(
                    modelId='anthropic.claude-3-5-sonnet-20240620-v1:0',
                    body=json.dumps({
                        "anthropic_version": "bedrock-2023-05-31",
                        "max_tokens": 1000,
                        "messages": [
                            {
                                "role": "user", 
                                "content": f"You are Zorix Agent, an AI coding assistant. Please respond to: {user_input}"
                            }
                        ]
                    })
                )
                
                result = json.loads(response['body'].read())
                ai_response = result['content'][0]['text']
                print(ai_response)
                print()
                
            except Exception as e:
                print(f"Error: {e}")
                print("💡 Try fixing your AWS credentials")
                print()
    
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("💡 Run: pip install boto3 python-dotenv")
    except Exception as e:
        print(f"❌ Error: {e}")

def main():
    """Main function."""
    print("🚀 Starting Zorix Agent AI Chat...")
    print()
    
    # Test connection first
    print("🔍 Testing AWS Bedrock connection...")
    if asyncio.run(test_bedrock_connection()):
        print()
        asyncio.run(chat_with_ai())
    else:
        print()
        print("🔧 To fix AWS connection:")
        print("1. Check your .env file has correct AWS credentials")
        print("2. Ensure you have Bedrock access in AWS Console")
        print("3. Try: aws bedrock list-foundation-models --region us-east-1")

if __name__ == "__main__":
    main()