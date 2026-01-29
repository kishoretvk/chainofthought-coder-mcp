"""
Enhanced MCP Demo - Demonstrates parallel execution and dependency tracking.
"""
import asyncio
import json
from memory_store_v2 import MemorySystemV2
from memory_store_v2.agents.orchestration_engine import OrchestrationEngine


async def demo():
    """Run the enhanced MCP demo."""
    print("=" * 60)
    print("ChainOfThought Coder MCP - Enhanced Edition")
    print("Parallel Execution with Dependency Tracking")
    print("=" * 60)
    
    # Initialize system
    memory = MemorySystemV2()
    orchestration = OrchestrationEngine(memory.tasks, max_parallel=4)
    
    # Create a session
    print("\n1. Creating session...")
    session_id = memory.sessions.create("Demo Session", {"purpose": "Enhanced MCP Demo"})
    print(f"   Session ID: {session_id}")
    
    # Create a complex task
    print("\n2. Creating complex task...")
    task_id = memory.tasks.create_main_task(
        session_id,
        "Build a Web Application",
        "Create a full-stack web application with user authentication, database integration, and responsive UI"
    )
    print(f"   Task ID: {task_id}")
    
    # Decompose the task
    print("\n3. Decomposing task into subtasks...")
    subtask_ids = await orchestration.decomposition_agent.decompose_task(session_id, task_id)
    print(f"   Created {len(subtask_ids)} subtasks:")
    for i, sub_id in enumerate(subtask_ids, 1):
        sub = memory.tasks.get(sub_id)
        print(f"      {i}. {sub['name']} ({sub_id})")
    
    # Analyze dependencies
    print("\n4. Analyzing dependencies...")
    deps = await orchestration.dependency_agent.analyze_dependencies(session_id, task_id)
    print(f"   Execution order: {deps.get('execution_order', [])}")
    print(f"   Critical path: {deps.get('critical_path', {})}")
    print(f"   Parallelizable groups: {deps.get('parallelizable_groups', [])}")
    
    # Get dependency graph for visualization
    print("\n5. Dependency graph:")
    graph = orchestration.dependency_agent.get_dependency_graph(session_id, task_id)
    print(f"   Nodes: {len(graph['nodes'])}")
    print(f"   Edges: {len(graph['edges'])}")
    
    # Create workflow
    print("\n6. Creating workflow...")
    workflow_id = await orchestration.create_workflow(
        session_id,
        "Web App Development Workflow",
        "Complete web application development workflow",
        {'task_id': task_id}
    )
    print(f"   Workflow ID: {workflow_id}")
    
    # Execute workflow with parallel execution
    print("\n7. Executing workflow (parallel execution)...")
    print("   Running tasks in parallel with dependency tracking...")
    
    # Set up progress callback
    progress_updates = []
    async def on_progress(task_id, progress, status):
        progress_updates.append({
            'task': task_id[:12] + '...',
            'progress': int(progress * 100),
            'status': status
        })
    
    orchestration.on_progress(task_id, on_progress)
    
    # Execute
    result = await orchestration.execute_workflow(workflow_id)
    
    print("\n8. Execution Results:")
    print(f"   Status: {result.get('status', 'unknown')}")
    print(f"   Total tasks: {result.get('total_tasks', 0)}")
    print(f"   Completed: {result.get('completed', 0)}")
    print(f"   Failed: {result.get('failed', 0)}")
    
    # Progress summary
    print("\n9. Progress History:")
    for update in progress_updates[:5]:
        print(f"   {update['task']}: {update['progress']}% - {update['status']}")
    if len(progress_updates) > 5:
        print(f"   ... and {len(progress_updates) - 5} more updates")
    
    # Get final status
    print("\n10. Final Workflow Status:")
    status = orchestration.get_workflow_status(workflow_id)
    if status:
        print(f"    Workflow Status: {status['workflow'].get('status', 'unknown')}")
        print(f"    Active Tasks: {len(status.get('active_tasks', []))}")
    
    # Progress prediction
    print("\n11. Progress Prediction:")
    prediction = memory.progress_tracker.predict_completion(session_id, task_id)
    print(f"    Remaining Tasks: {prediction.get('remaining_tasks', 0)}")
    print(f"    Estimated Time: {prediction.get('estimated_minutes', 0):.1f} minutes")
    print(f"    Completion: {prediction.get('completion_percentage', 0):.1f}%")
    
    # System stats
    print("\n12. System Statistics:")
    stats = memory.get_stats()
    print(f"    Sessions: {stats.get('sessions', 0)}")
    print(f"    Tasks: {stats.get('tasks', 0)}")
    print(f"    Checkpoints: {stats.get('checkpoints', 0)}")
    print(f"    Long-term Memories: {stats.get('long_term_memory', 0)}")
    
    print("\n" + "=" * 60)
    print("Demo Complete!")
    print("=" * 60)
    
    # Cleanup
    memory.close()


async def demo_individual_agents():
    """Demo individual agent capabilities."""
    print("\n\n" + "=" * 60)
    print("Individual Agent Capabilities Demo")
    print("=" * 60)
    
    memory = MemorySystemV2()
    orchestration = OrchestrationEngine(memory.tasks, max_parallel=2)
    
    # Demo task classification
    print("\n1. Task Classification:")
    tasks = [
        {"name": "Code Review", "description": "Review the codebase for issues"},
        {"name": "Unit Tests", "description": "Write comprehensive unit tests"},
        {"name": "API Integration", "description": "Integrate with external API"},
        {"name": "Performance Tuning", "description": "Optimize database queries"}
    ]
    
    for task_data in tasks:
        task_id = memory.tasks.create_main_task(
            "demo_session",
            task_data["name"],
            task_data["description"]
        )
        task = memory.tasks.get(task_id)
        task_type = orchestration.decomposition_agent.classify_task(task)
        complexity = orchestration.decomposition_agent.analyze_complexity(task)
        print(f"   {task_data['name']}: {task_type} (complexity: {complexity:.1f})")
    
    # Demo dependency patterns
    print("\n2. Dependency Patterns:")
    print("   Testing -> Code Generation: Tests depend on code")
    print("   Integration -> Testing: Integration tests run after integration")
    print("   Deployment -> Documentation: Docs updated after deployment")
    
    # Demo subtask templates
    print("\n3. Subtask Templates Available:")
    templates = list(orchestration.decomposition_agent.SUBTASK_TEMPLATES.keys())
    for template in templates:
        subtasks = len(orchestration.decomposition_agent.SUBTASK_TEMPLATES[template])
        print(f"   {template}: {subtasks} subtasks")
    
    memory.close()


if __name__ == "__main__":
    asyncio.run(demo())
    asyncio.run(demo_individual_agents())
