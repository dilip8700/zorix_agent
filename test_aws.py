#!/usr/bin/env python3
"""Test AWS Bedrock connection"""

import os
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

def test_aws_connection():
    """Test AWS Bedrock connection with current credentials."""
    
    print("🔍 Testing AWS Bedrock Connection...")
    print("=" * 50)
    
    # Load environment variables
    try:
        from dotenv import load_dotenv
        load_dotenv()
        print("✅ Loaded .env file")
    except ImportError:
        print("⚠️  python-dotenv not installed, using system environment")
    
    # Check credentials
    access_key = os.getenv('AWS_ACCESS_KEY_ID')
    secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
    region = os.getenv('BEDROCK_REGION', 'us-east-1')
    
    print(f"🔑 Access Key: {access_key[:10]}..." if access_key else "❌ No access key found")
    print(f"🔑 Secret Key: {'*' * 10}..." if secret_key else "❌ No secret key found")
    print(f"🌍 Region: {region}")
    print()
    
    if not access_key or not secret_key:
        print("❌ AWS credentials not found in environment")
        print("💡 Make sure your .env file has:")
        print("   AWS_ACCESS_KEY_ID=your_key")
        print("   AWS_SECRET_ACCESS_KEY=your_secret")
        return False
    
    try:
        # Test basic AWS connection
        print("🧪 Testing AWS STS (Security Token Service)...")
        sts_client = boto3.client('sts', region_name=region)
        identity = sts_client.get_caller_identity()
        print(f"✅ AWS Identity: {identity.get('Arn', 'Unknown')}")
        print()
        
        # Test Bedrock connection
        print("🧪 Testing AWS Bedrock...")
        bedrock_client = boto3.client('bedrock', region_name=region)
        models = bedrock_client.list_foundation_models()
        
        print(f"✅ Bedrock Connected! Found {len(models['modelSummaries'])} models")
        
        # Check for Claude model
        claude_models = [m for m in models['modelSummaries'] if 'claude' in m['modelId'].lower()]
        if claude_models:
            print(f"✅ Found {len(claude_models)} Claude models")
            for model in claude_models[:3]:  # Show first 3
                print(f"   - {model['modelId']}")
        else:
            print("⚠️  No Claude models found - you may need to request access")
        
        print()
        print("🎉 AWS Bedrock is ready to use!")
        return True
        
    except NoCredentialsError:
        print("❌ AWS credentials not found")
        print("💡 Check your .env file or AWS CLI configuration")
        return False
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        
        print(f"❌ AWS Error: {error_code}")
        print(f"📝 Message: {error_message}")
        
        if error_code == 'UnrecognizedClientException':
            print("💡 This usually means:")
            print("   - Invalid access key or secret key")
            print("   - Credentials are expired")
            print("   - Wrong region")
        elif error_code == 'AccessDeniedException':
            print("💡 This usually means:")
            print("   - No permission to access Bedrock")
            print("   - Need to request model access in AWS console")
        
        return False
        
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    test_aws_connection()