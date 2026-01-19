"""
Comprehensive test suite for Memory System V2.
Tests all managers and integration scenarios.
"""
import pytest
import tempfile
import shutil
import json
from memory_store_v2 import MemorySystemV2


class TestMemorySystemV2:
    """Test suite for the new hybrid memory system."""
    
    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.memory = MemorySystemV2(self.temp_dir)
    
    def teardown_method(self):
        """Clean up test environment."""
        self.memory.close()
        shutil.rmtree(self.temp_dir)
    
    def test_session_lifecycle(self):
        """Test session creation, retrieval, and lifecycle."""
        # Create session
        session_id = self.memory.sessions.create("Test Session", {"project": "test"})
        assert session_id.startswith("sess_")
        
        # Get session
        session = self.memory.sessions.get(session_id)
        assert session['name'] == "Test Session"
        assert session['status'] == "active"
        assert json.loads(session['metadata'])['project'] == "test"
        
        # List sessions
        sessions = self.memory.sessions.list()
        assert len(sessions) == 1
        
        # Update session
        self.memory.sessions.update(session_id, status="paused")
        session = self.memory.sessions.get(session_id)
        assert session['status'] == "paused"
        
        # Archive session
        self.memory.sessions.archive(session_id)
        session = self.memory.sessions.get(session_id)
        assert session['status'] == "archived"
    
    def test_hierarchical_tasks(self):
        """Test task hierarchy with automatic progress aggregation."""
        session_id = self.memory.sessions.create("Task Test")
        
        # Create main task
        main_id = self.memory.tasks.create_main_task(
            session_id, "Build App", "Full stack application"
        )
        
        # Create sub-tasks
        sub1 = self.memory.tasks.create_subtask(
            session_id, main_id, "Backend", "API layer"
        )
        sub2 = self.memory.tasks.create_subtask(
            session_id, main_id, "Frontend", "UI layer"
        )
        sub3 = self.memory.tasks.create_subtask(
            session_id, main_id, "Database", "Data layer"
        )
        
        # Update sub-task progress
        self.memory.tasks.update_progress(sub1, 1.0, "completed")
        self.memory.tasks.update_progress(sub2, 0.5, "in_progress")
        self.memory.tasks.update_progress(sub3, 0.0, "pending")
        
        # Get tree
        tree = self.memory.tasks.get_tree(session_id)
        main_task = tree['main_tasks'][0]
        
        # Verify automatic aggregation
        assert main_task['progress'] == 0.5  # (1.0 + 0.5 + 0.0) / 3
        assert main_task['status'] == "in_progress"
        assert len(main_task['subtasks']) == 3
        
        # Verify sub-tasks
        assert main_task['subtasks'][0]['progress'] == 1.0
        assert main_task['subtasks'][1]['progress'] == 0.5
        assert main_task['subtasks'][2]['progress'] == 0.0
    
    def test_long_term_memory(self):
        """Test long-term memory storage and retrieval."""
        session_id = self.memory.sessions.create("Memory Test")
        
        # Store knowledge
        mem_id1 = self.memory.memory.store_long_term(
            session_id, "knowledge",
            {"pattern": "microservices", "best_practice": "event-driven"},
            tags=["architecture", "backend"],
            confidence=0.9,
            source="experience"
        )
        
        # Store insight
        mem_id2 = self.memory.memory.store_long_term(
            session_id, "insight",
            {"realization": "caching improves performance"},
            tags=["performance"],
            confidence=0.8
        )
        
        # Store global knowledge (no session_id)
        mem_id3 = self.memory.memory.store_long_term(
            None, "knowledge",
            {"pattern": "singleton", "use_case": "shared resources"},
            tags=["design_pattern"],
            confidence=0.95
        )
        
        # Retrieve by type
        knowledge = self.memory.memory.retrieve_long_term(
            session_id, memory_type="knowledge"
        )
        assert len(knowledge) == 1
        assert knowledge[0]['content']['pattern'] == "microservices"
        
        # Retrieve all
        all_mem = self.memory.memory.retrieve_long_term(session_id)
        assert len(all_mem) == 2
        
        # Search by query
        results = self.memory.memory.retrieve_long_term(
            session_id, query="performance"
        )
        assert len(results) == 1
    
    def test_short_term_memory(self):
        """Test short-term (working) memory."""
        session_id = self.memory.sessions.create("ShortTerm Test")
        
        # Store short-term memory
        self.memory.memory.store_short_term(
            session_id,
            active_context={"current_task": "api_design", "endpoint": "/users"},
            recent_actions=[
                {"action": "created_endpoint", "timestamp": 1234567890},
                {"action": "added_auth", "timestamp": 1234567891}
            ],
            focus_area="authentication",
            temporary_state={"draft_schema": {"type": "object"}}
        )
        
        # Retrieve
        stm = self.memory.memory.get_short_term(session_id)
        assert stm['focus_area'] == "authentication"
        assert stm['active_context']['endpoint'] == "/users"
        assert len(stm['recent_actions']) == 2
        
        # Push context
        self.memory.memory.push_context(session_id, {"new_field": "value"})
        stm = self.memory.memory.get_short_term(session_id)
        assert stm['active_context']['new_field'] == "value"
        assert stm['active_context']['endpoint'] == "/users"  # preserved
        
        # Push action
        self.memory.memory.push_action(session_id, {"action": "test"})
        stm = self.memory.memory.get_short_term(session_id)
        assert len(stm['recent_actions']) == 3
        assert stm['recent_actions'][-1]['action'] == "test"
        
        # Clear
        self.memory.memory.clear_short_term(session_id)
        stm = self.memory.memory.get_short_term(session_id)
        assert stm is None
    
    def test_checkpoint_overall(self):
        """Test overall session checkpoint."""
        session_id = self.memory.sessions.create("Checkpoint Test")
        
        # Setup tasks and memory
        task_id = self.memory.tasks.create_main_task(session_id, "Main Task")
        self.memory.tasks.update_progress(task_id, 0.5, "in_progress")
        
        self.memory.memory.store_long_term(
            session_id, "knowledge",
            {"info": "test"}, tags=["test"]
        )
        
        self.memory.memory.store_short_term(
            session_id, active_context={"key": "value"}
        )
        
        # Create checkpoint
        cp_id = self.memory.checkpoints.create_overall(
            session_id, tags=["test", "overall"], metadata={"version": 1}
        )
        
        # Verify checkpoint exists
        checkpoint = self.memory.checkpoints.get(cp_id)
        assert checkpoint is not None
        assert checkpoint['level'] == 'overall'
        assert checkpoint['session_id'] == session_id
        
        # Verify snapshot content
        snapshot = checkpoint['snapshot']
        assert snapshot['type'] == 'overall'
        assert snapshot['tasks']['main_tasks'][0]['progress'] == 0.5
        assert len(snapshot['long_term_memory']) == 1
        assert snapshot['short_term_memory']['active_context']['key'] == "value"
        
        # List checkpoints
        checkpoints = self.memory.checkpoints.list(session_id)
        assert len(checkpoints) == 1
        assert checkpoints[0]['checkpoint_id'] == cp_id
    
    def test_checkpoint_subtask(self):
        """Test sub-task checkpoint."""
        session_id = self.memory.sessions.create("Subtask CP Test")
        main_id = self.memory.tasks.create_main_task(session_id, "Main")
        sub_id = self.memory.tasks.create_subtask(session_id, main_id, "Subtask")

        self.memory.tasks.update_progress(sub_id, 0.75, "in_progress")

        # Create subtask checkpoint
        cp_id = self.memory.checkpoints.create_subtask(
            sub_id, tags=["subtask"], metadata={"stage": "mid"}
        )

        checkpoint = self.memory.checkpoints.get(cp_id)
        assert checkpoint['level'] == 'subtask'
        assert checkpoint['task_id'] == sub_id

        snapshot = checkpoint['snapshot']
        assert snapshot['type'] == 'subtask'
        # For a subtask checkpoint, task_details is the subtask itself
        assert snapshot['task_details']['progress'] == 0.75
        assert snapshot['task_details']['status'] == 'in_progress'
    
    def test_checkpoint_stage(self):
        """Test stage checkpoint."""
        session_id = self.memory.sessions.create("Stage CP Test")
        task_id = self.memory.tasks.create_main_task(session_id, "Task")
        
        self.memory.tasks.update_progress(task_id, 0.3, "in_progress")
        self.memory.memory.store_short_term(
            session_id, active_context={"stage": "design"}
        )
        
        # Create stage checkpoint
        cp_id = self.memory.checkpoints.create_stage(
            task_id, "design_phase", tags=["design"], metadata={"phase": 1}
        )
        
        checkpoint = self.memory.checkpoints.get(cp_id)
        assert checkpoint['level'] == 'stage'
        
        snapshot = checkpoint['snapshot']
        assert snapshot['type'] == 'stage'
        assert snapshot['stage_name'] == 'design_phase'
        assert snapshot['current_state']['task']['progress'] == 0.3
    
    def test_checkpoint_restore(self):
        """Test checkpoint restoration."""
        session_id = self.memory.sessions.create("Restore Test")
        
        # Create initial state
        task_id = self.memory.tasks.create_main_task(session_id, "Task")
        self.memory.memory.store_long_term(
            session_id, "knowledge", {"data": "original"}
        )
        
        # Create checkpoint
        cp_id = self.memory.checkpoints.create_overall(session_id)
        
        # Modify state
        self.memory.tasks.update_progress(task_id, 0.8, "completed")
        self.memory.memory.store_long_term(
            session_id, "knowledge", {"data": "modified"}
        )
        
        # Restore
        success = self.memory.checkpoints.restore(session_id, cp_id)
        assert success
        
        # Verify restoration
        task = self.memory.tasks.get(task_id)
        assert task['progress'] == 0.0  # Back to original
        assert task['status'] == 'pending'
        
        memories = self.memory.memory.retrieve_long_term(session_id)
        assert len(memories) == 1
        assert memories[0]['content']['data'] == "original"
    
    def test_checkpoint_diff(self):
        """Test checkpoint comparison."""
        session_id = self.memory.sessions.create("Diff Test")
        task_id = self.memory.tasks.create_main_task(session_id, "Task")
        
        # First checkpoint
        cp1 = self.memory.checkpoints.create_overall(session_id)
        
        # Modify
        self.memory.tasks.update_progress(task_id, 0.5, "in_progress")
        self.memory.tasks.create_subtask(session_id, task_id, "Subtask")
        
        # Second checkpoint
        cp2 = self.memory.checkpoints.create_overall(session_id)
        
        # Compare
        diff = self.memory.checkpoints.diff(cp1, cp2)
        
        assert diff['checkpoint_1'] == cp1
        assert diff['checkpoint_2'] == cp2
        assert len(diff['changes']['tasks']) > 0
        assert any("CHANGED" in change for change in diff['changes']['tasks'])
    
    def test_checkpoint_cleanup(self):
        """Test old checkpoint cleanup."""
        session_id = self.memory.sessions.create("Cleanup Test")
        
        # Create multiple checkpoints
        for i in range(15):
            self.memory.checkpoints.create_overall(session_id, tags=[f"cp{i}"])
        
        # Cleanup (keep last 5)
        deleted = self.memory.checkpoints.cleanup_old(session_id, keep_last=5)
        assert deleted == 10
        
        # Verify
        checkpoints = self.memory.checkpoints.list(session_id)
        assert len(checkpoints) == 5
    
    def test_dependencies(self):
        """Test task dependencies."""
        session_id = self.memory.sessions.create("Dependency Test")
        
        task1 = self.memory.tasks.create_main_task(session_id, "Task 1")
        task2 = self.memory.tasks.create_main_task(session_id, "Task 2")
        
        # Add dependency
        success = self.memory.tasks.add_dependency(task2, task1)
        assert success
        
        task = self.memory.tasks.get(task2)
        deps = json.loads(task['dependencies'])
        assert task1 in deps
    
    def test_stats(self):
        """Test system statistics."""
        session_id = self.memory.sessions.create("Stats Test")
        
        for i in range(3):
            self.memory.tasks.create_main_task(session_id, f"Task {i}")
        
        for i in range(5):
            self.memory.memory.store_long_term(
                session_id, "knowledge", {"data": f"mem{i}"}
            )
        
        for i in range(2):
            self.memory.checkpoints.create_overall(session_id)
        
        stats = self.memory.get_stats()
        
        assert stats['sessions'] == 1
        assert stats['tasks'] == 3
        assert stats['checkpoints'] == 2
        assert stats['long_term_memory'] == 5
    
    def test_integration_full_workflow(self):
        """Test complete workflow: session -> tasks -> memory -> checkpoints."""
        # 1. Create session
        session_id = self.memory.sessions.create("Web App Project", {
            "client": "Acme Corp",
            "deadline": "2024-12-31"
        })
        
        # 2. Create task hierarchy
        design = self.memory.tasks.create_main_task(
            session_id, "Design Phase", "UI/UX and architecture"
        )
        
        ui = self.memory.tasks.create_subtask(session_id, design, "UI Design")
        api = self.memory.tasks.create_subtask(session_id, design, "API Design")
        
        # 3. Store knowledge
        self.memory.memory.store_long_term(
            session_id, "knowledge",
            {"pattern": "responsive_design", "framework": "tailwind"},
            tags=["frontend", "design"],
            confidence=0.9
        )
        
        # 4. Work on tasks
        self.memory.tasks.update_progress(ui, 0.5, "in_progress")
        self.memory.memory.store_short_term(
            session_id,
            active_context={"current_file": "design.fig"},
            focus_area="mobile_layout"
        )
        
        # 5. Create checkpoint
        cp1 = self.memory.checkpoints.create_overall(
            session_id, tags=["mid_design"], metadata={"milestone": "50%"}
        )
        
        # 6. Continue work
        self.memory.tasks.update_progress(ui, 1.0, "completed")
        self.memory.tasks.update_progress(api, 0.3, "in_progress")
        
        # 7. Create another checkpoint
        cp2 = self.memory.checkpoints.create_overall(
            session_id, tags=["design_complete"], metadata={"milestone": "75%"}
        )
        
        # 8. Verify state
        tree = self.memory.tasks.get_tree(session_id)
        main = tree['main_tasks'][0]
        
        assert main['progress'] == 0.65  # (1.0 + 0.3) / 2
        assert len(main['subtasks']) == 2
        
        # 9. Verify checkpoints
        checkpoints = self.memory.checkpoints.list(session_id)
        assert len(checkpoints) == 2
        
        # 10. Verify memory
        memories = self.memory.memory.retrieve_long_term(session_id)
        assert len(memories) == 1
        
        # 11. Test restore
        self.memory.checkpoints.restore(session_id, cp1)
        task = self.memory.tasks.get(ui)
        assert task['progress'] == 0.5  # Restored to 50%
        
        print("✅ Full workflow test passed!")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
