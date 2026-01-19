#!/usr/bin/env python3
"""
Demo script showcasing Memory System V2 capabilities.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import json
from memory_store_v2 import MemorySystemV2


def print_section(title):
    """Print a formatted section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def demo():
    """Run the complete demo."""
    print("🚀 Memory System V2 - Interactive Demo")
    print("   Hybrid SQLite + JSON Architecture")
    
    # Initialize system
    memory = MemorySystemV2("./demo_storage")
    
    try:
        # 1. Session Management
        print_section("1. Session Management")
        
        session_id = memory.sessions.create("Web App Development", {
            "client": "Acme Corp",
            "deadline": "2024-12-31",
            "priority": "high"
        })
        print(f"✅ Created session: {session_id}")
        
        sessions = memory.sessions.list()
        print(f"📋 Total sessions: {len(sessions)}")
        print(f"   Active: {len([s for s in sessions if s['status'] == 'active'])}")
        
        # 2. Task Hierarchy
        print_section("2. Task Hierarchy with Auto-Aggregation")
        
        # Main task
        design_phase = memory.tasks.create_main_task(
            session_id, 
            "Design Phase", 
            "UI/UX and system architecture"
        )
        print(f"✅ Main task created: {design_phase}")
        
        # Sub-tasks
        ui_design = memory.tasks.create_subtask(
            session_id, design_phase, "UI Design", "Wireframes and mockups"
        )
        api_design = memory.tasks.create_subtask(
            session_id, design_phase, "API Design", "REST endpoints and schemas"
        )
        db_design = memory.tasks.create_subtask(
            session_id, design_phase, "Database Design", "Schema and relationships"
        )
        print(f"✅ Created 3 sub-tasks")
        
        # Update progress
        memory.tasks.update_progress(ui_design, 0.5, "in_progress")
        memory.tasks.update_progress(api_design, 0.3, "in_progress")
        memory.tasks.update_progress(db_design, 0.0, "pending")
        
        # Get tree
        tree = memory.tasks.get_tree(session_id)
        main = tree['main_tasks'][0]
        print(f"\n📊 Progress: {main['progress']*100:.0f}% (auto-calculated)")
        print(f"   Status: {main['status']}")
        print(f"   Sub-tasks: {len(main['subtasks'])}")
        
        for sub in main['subtasks']:
            print(f"   - {sub['name']}: {sub['progress']*100:.0f}% ({sub['status']})")
        
        # 3. Long-term Memory
        print_section("3. Long-term Memory (Knowledge Base)")
        
        # Store knowledge
        memory.memory.store_long_term(
            session_id, "knowledge",
            {"pattern": "responsive_design", "best_practice": "mobile-first"},
            tags=["frontend", "design"],
            confidence=0.95,
            source="experience"
        )
        
        memory.memory.store_long_term(
            session_id, "insight",
            {"realization": "caching improves API performance by 3x"},
            tags=["performance", "backend"],
            confidence=0.9
        )
        
        # Global knowledge (shared across sessions)
        memory.memory.store_long_term(
            None, "knowledge",
            {"pattern": "singleton", "use_case": "shared resources"},
            tags=["design_pattern"],
            confidence=1.0
        )
        
        # Retrieve
        knowledge = memory.memory.retrieve_long_term(
            session_id, memory_type="knowledge"
        )
        print(f"✅ Stored {len(knowledge)} session-specific knowledge items")
        
        all_mem = memory.memory.retrieve_long_term(session_id)
        print(f"✅ Total memories for session: {len(all_mem)}")
        
        # Search
        results = memory.memory.retrieve_long_term(
            session_id, query="performance"
        )
        print(f"🔍 Search 'performance': {len(results)} results")
        
        # 4. Short-term Memory
        print_section("4. Short-term Memory (Working Context)")
        
        memory.memory.store_short_term(
            session_id,
            active_context={
                "current_task": "ui_design",
                "current_file": "mockup.fig",
                "tool": "Figma"
            },
            recent_actions=[
                {"action": "created_wireframe", "timestamp": 1234567890},
                {"action": "added_color_scheme", "timestamp": 1234567891}
            ],
            focus_area="mobile_layout",
            temporary_state={"draft": {"colors": ["#FF5733", "#33FF57"]}}
        )
        
        stm = memory.memory.get_short_term(session_id)
        print(f"✅ Working context stored")
        print(f"   Focus: {stm['focus_area']}")
        print(f"   Current file: {stm['active_context']['current_file']}")
        print(f"   Recent actions: {len(stm['recent_actions'])}")
        
        # Push context
        memory.memory.push_context(session_id, {"new_field": "responsive_breakpoint"})
        stm = memory.memory.get_short_term(session_id)
        print(f"✅ Context updated: {len(stm['active_context'])} fields")
        
        # Push action
        memory.memory.push_action(session_id, {"action": "added_typography"})
        stm = memory.memory.get_short_term(session_id)
        print(f"✅ Action logged: {len(stm['recent_actions'])} total actions")
        
        # 5. Checkpoints - Overall
        print_section("5. Checkpoints - Overall Session")
        
        cp1 = memory.checkpoints.create_overall(
            session_id, 
            tags=["initial", "design_start"],
            metadata={"milestone": "project_start"}
        )
        print(f"✅ Checkpoint 1: {cp1}")
        
        # Continue work
        memory.tasks.update_progress(ui_design, 1.0, "completed")
        memory.tasks.update_progress(api_design, 0.7, "in_progress")
        
        cp2 = memory.checkpoints.create_overall(
            session_id,
            tags=["midpoint", "design_complete"],
            metadata={"milestone": "50%"}
        )
        print(f"✅ Checkpoint 2: {cp2}")
        
        # List checkpoints
        checkpoints = memory.checkpoints.list(session_id)
        print(f"\n📋 Total checkpoints: {len(checkpoints)}")
        for cp in checkpoints:
            print(f"   - {cp['checkpoint_id']}: {cp['level']} ({cp['tags']})")
        
        # 6. Checkpoints - Subtask & Stage
        print_section("6. Checkpoints - Subtask & Stage")
        
        # Subtask checkpoint
        cp_sub = memory.checkpoints.create_subtask(
            ui_design,
            tags=["ui_complete"],
            metadata={"phase": "final"}
        )
        print(f"✅ Subtask checkpoint: {cp_sub}")
        
        # Stage checkpoint
        cp_stage = memory.checkpoints.create_stage(
            api_design,
            "authentication_design",
            tags=["auth", "security"],
            metadata={"stage": 1}
        )
        print(f"✅ Stage checkpoint: {cp_stage}")
        
        # 7. Checkpoint Diff
        print_section("7. Checkpoint Comparison")
        
        diff = memory.checkpoints.diff(cp1, cp2)
        print(f"📊 Changes between checkpoints:")
        print(f"   Time difference: {diff['timestamp_diff']:.2f}s")
        print(f"   Task changes: {len(diff['changes']['tasks'])}")
        for change in diff['changes']['tasks']:
            print(f"   - {change}")
        
        # 8. Checkpoint Restore
        print_section("8. Checkpoint Restore")
        
        # Current state
        current_task = memory.tasks.get(ui_design)
        print(f"Current UI Design progress: {current_task['progress']*100:.0f}%")
        
        # Restore to checkpoint 1
        memory.checkpoints.restore(session_id, cp1)
        restored_task = memory.tasks.get(ui_design)
        print(f"✅ Restored to checkpoint 1")
        print(f"   UI Design progress: {restored_task['progress']*100:.0f}%")
        
        # 9. Dependencies
        print_section("9. Task Dependencies")
        
        task1 = memory.tasks.create_main_task(session_id, "Backend API")
        task2 = memory.tasks.create_main_task(session_id, "Frontend Integration")
        
        memory.tasks.add_dependency(task2, task1)
        task = memory.tasks.get(task2)
        deps = json.loads(task['dependencies'])
        print(f"✅ Task dependency created")
        print(f"   '{task2}' depends on: {deps}")
        
        # 10. Cleanup
        print_section("10. Checkpoint Cleanup")
        
        # Create more checkpoints
        for i in range(5):
            memory.checkpoints.create_overall(session_id, tags=[f"auto_{i}"])
        
        before = len(memory.checkpoints.list(session_id))
        deleted = memory.checkpoints.cleanup_old(session_id, keep_last=3)
        after = len(memory.checkpoints.list(session_id))
        
        print(f"✅ Cleanup complete")
        print(f"   Before: {before} checkpoints")
        print(f"   Deleted: {deleted}")
        print(f"   After: {after} checkpoints")
        
        # 11. Statistics
        print_section("11. System Statistics")
        
        stats = memory.get_stats()
        print(f"📊 System Overview:")
        print(f"   Sessions: {stats['sessions']}")
        print(f"   Tasks: {stats['tasks']}")
        print(f"   Checkpoints: {stats['checkpoints']}")
        print(f"   Long-term Memories: {stats['long_term_memory']}")
        
        print("\n" + "="*60)
        print("🎉 Demo Complete!")
        print("="*60)
        print("\nKey Takeaways:")
        print("✅ Hierarchical task management with auto-aggregation")
        print("✅ Dual-tier memory (long-term + short-term)")
        print("✅ Multi-level checkpoints (overall/subtask/stage)")
        print("✅ Fast SQLite queries + flexible JSON snapshots")
        print("✅ Transaction safety and data integrity")
        
    finally:
        # Cleanup
        memory.close()
        print("\n💾 Demo data saved to: ./demo_storage")
        print("   (You can delete this directory to clean up)")


if __name__ == "__main__":
    demo()
