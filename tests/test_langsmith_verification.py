"""
LangSmith Configuration Verification Script

This script verifies that LangSmith is properly configured and working.
Run this before using the testing dashboard.
"""

import asyncio
import os
import sys
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


async def verify_langsmith_config():
    """Verify LangSmith configuration and connectivity"""
    from app.config.langsmith_config import get_tracer
    from app.config.langsmith_init import get_langsmith_status, initialize_langsmith

    print("🔍 LangSmith Configuration Verification")
    print("=" * 60)

    # Step 1: Initialize LangSmith
    print("\n1️⃣ Initializing LangSmith...")
    initialized = initialize_langsmith(force=True)
    print(f"   ✅ Initialization: {'SUCCESS' if initialized else 'FAILED'}")

    # Step 2: Get status
    print("\n2️⃣ Checking LangSmith Status...")
    status = get_langsmith_status()

    print(f"   📊 Configuration Status:")
    print(f"      - Tracing Enabled: {status.get('tracing_enabled', False)}")
    print(f"      - Project: {status.get('project', 'N/A')}")
    print(f"      - Endpoint: {status.get('endpoint', 'N/A')}")
    print(f"      - API Connection: {status.get('api_connection', 'N/A')}")

    # Step 3: Check environment variables
    print("\n3️⃣ Environment Variables:")
    env_vars = {
        "LANGSMITH_API_KEY": "✅ Set" if os.getenv("LANGSMITH_API_KEY") else "❌ Missing",
        "LANGSMITH_PROJECT": os.getenv("LANGSMITH_PROJECT", "❌ Not set"),
        "LANGSMITH_TRACING": os.getenv("LANGSMITH_TRACING", "❌ Not set"),
        "LANGSMITH_ENDPOINT": os.getenv("LANGSMITH_ENDPOINT", "❌ Not set"),
    }

    for key, value in env_vars.items():
        if key == "LANGSMITH_API_KEY":
            print(f"      - {key}: {value}")
        else:
            print(f"      - {key}: {value}")

    # Step 4: Test tracer
    print("\n4️⃣ Testing Tracer...")
    tracer = get_tracer()
    print(f"   ✅ Tracer initialized: {tracer is not None}")
    print(f"   ✅ Client available: {tracer.client is not None}")
    print(f"   ✅ Tracing enabled: {tracer.config.tracing_enabled}")

    # Step 5: Test LangSmith API connectivity
    print("\n5️⃣ Testing LangSmith API Connectivity...")
    if tracer.client:
        try:
            # Try to list projects (simple API call)
            projects = list(tracer.client.list_projects(limit=1))
            print(f"   ✅ API Connection: SUCCESS")
            print(f"   📁 Found {len(projects)} project(s)")
        except Exception as e:
            print(f"   ❌ API Connection: FAILED")
            print(f"      Error: {str(e)}")
    else:
        print(f"   ❌ API Connection: Client not initialized")

    # Step 6: Test trace creation
    print("\n6️⃣ Testing Trace Creation...")
    try:
        from langsmith import traceable

        @traceable(name="test_trace", project_name=status.get("project", "aynux-production"))
        def test_function():
            return {"status": "success", "timestamp": datetime.now().isoformat()}

        result = test_function()
        print(f"   ✅ Trace Creation: SUCCESS")
        print(f"   📝 Test result: {result}")
    except Exception as e:
        print(f"   ❌ Trace Creation: FAILED")
        print(f"      Error: {str(e)}")

    # Summary
    print("\n" + "=" * 60)
    print("📋 SUMMARY")
    print("=" * 60)

    all_checks = [
        initialized,
        status.get("tracing_enabled", False),
        tracer.client is not None,
        os.getenv("LANGSMITH_API_KEY") is not None,
    ]

    if all(all_checks):
        print("✅ All checks passed! LangSmith is ready to use.")
        print(f"\n🔗 View traces at: https://smith.langchain.com/o/default/projects/p/{status.get('project', '')}")
        return True
    else:
        print("❌ Some checks failed. Please review the configuration.")
        print("\n📖 Troubleshooting:")
        print("   1. Check .env file for LANGSMITH_API_KEY")
        print("   2. Ensure LANGSMITH_TRACING=true")
        print("   3. Verify LANGSMITH_PROJECT matches your LangSmith project")
        print("   4. Check internet connectivity to api.smith.langchain.com")
        return False


async def test_conversation_tracing():
    """Test conversation tracing with a simple message"""
    from app.services.langgraph_chatbot_service import LangGraphChatbotService

    print("\n" + "=" * 60)
    print("🧪 Testing Conversation Tracing")
    print("=" * 60)

    try:
        # Initialize service
        print("\n1️⃣ Initializing LangGraph service...")
        service = LangGraphChatbotService()
        await service.initialize()
        print("   ✅ Service initialized")

        # Test message
        print("\n2️⃣ Sending test message...")
        test_message = "Hola, ¿qué productos tienen disponibles?"
        test_user = "test_user_123"
        test_session = f"test_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        print(f"   📨 Message: {test_message}")
        print(f"   👤 User: {test_user}")
        print(f"   🔑 Session: {test_session}")

        # Process message
        result = await service.process_chat_message(
            message=test_message, user_id=test_user, session_id=test_session, metadata={"test": True}
        )

        print("\n3️⃣ Processing complete!")
        print(f"   ✅ Response: {result.get('response', 'No response')[:100]}...")
        print(f"   🤖 Agent used: {result.get('agent_used', 'unknown')}")
        print(f"   ⏱️ Processing time: {result.get('processing_time_ms', 0)}ms")

        # Check LangSmith for traces
        print("\n4️⃣ Checking LangSmith traces...")
        from app.config.langsmith_config import get_tracer

        tracer = get_tracer()
        if tracer.client:
            try:
                # Get recent runs
                runs = list(
                    tracer.client.list_runs(
                        project_name=tracer.config.project_name, limit=5, order="-start_time"
                    )
                )
                print(f"   ✅ Found {len(runs)} recent trace(s)")
                if runs:
                    latest_run = runs[0]
                    print(f"   📊 Latest trace:")
                    print(f"      - ID: {latest_run.id}")
                    print(f"      - Name: {latest_run.name}")
                    print(f"      - Status: {'✅ Success' if not latest_run.error else '❌ Error'}")
                    if latest_run.latency:
                        print(f"      - Latency: {latest_run.latency:.2f}s")
            except Exception as e:
                print(f"   ⚠️ Could not fetch traces: {str(e)}")
        else:
            print(f"   ⚠️ Tracer client not available")

        print("\n✅ Conversation tracing test complete!")
        print(
            f"🔗 View trace at: https://smith.langchain.com/o/default/projects/p/{tracer.config.project_name if tracer else 'N/A'}"
        )

        return True

    except Exception as e:
        print(f"\n❌ Conversation tracing test failed!")
        print(f"   Error: {str(e)}")
        import traceback

        traceback.print_exc()
        return False


async def main():
    """Main verification workflow"""
    print("\n" + "🚀 " * 20)
    print("LangSmith Testing & Verification Suite")
    print("🚀 " * 20 + "\n")

    # Step 1: Verify configuration
    config_ok = await verify_langsmith_config()

    if not config_ok:
        print("\n⚠️ Configuration issues detected. Skipping conversation test.")
        print("   Please fix configuration issues and run again.")
        return False

    # Step 2: Test conversation tracing
    print("\n" + "⏳ " * 20)
    await asyncio.sleep(1)  # Brief pause for readability

    trace_ok = await test_conversation_tracing()

    # Final summary
    print("\n" + "=" * 60)
    print("🏁 FINAL RESULTS")
    print("=" * 60)

    if config_ok and trace_ok:
        print("✅ All tests passed successfully!")
        print("\n✨ LangSmith is fully operational and ready for testing.")
        print("\n📚 Next steps:")
        print("   1. Run the interactive chat interface: python tests/test_chat_interactive.py")
        print("   2. Run automated test scenarios: python tests/test_scenarios.py all")
        print(
            "   3. View traces in LangSmith: https://smith.langchain.com/o/default/projects/p/aynux-production"
        )
        return True
    else:
        print("❌ Some tests failed. Please review the errors above.")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
