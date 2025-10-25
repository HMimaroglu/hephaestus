import logging
from typing import Dict, Any
from backend.llm import llm_adapter
from backend.schemas import TaskMessage

logger = logging.getLogger(__name__)


class ResearcherRole:

    def __init__(self):
        self.name = "researcher"
        self.state: Dict[str, Any] = {
            "research_history": [],
            "knowledge_base": {}
        }

    async def initialize(self):
        logger.info(f"Initialized {self.name} role")

    async def cleanup(self):
        logger.info(f"Cleaning up {self.name} role")

    async def execute(self, task: TaskMessage) -> dict:
        logger.info(f"Researcher processing task: {task.task_id}")

        system_prompt = """You are a research assistant in a distributed AI system.
Your job is to gather information, analyze data, and provide well-researched answers.
Be thorough, cite sources when possible, and structure your findings clearly."""

        try:
            result = await llm_adapter.generate(
                prompt=task.prompt,
                system_prompt=system_prompt,
                temperature=0.7,
                max_tokens=2000
            )

            self.state["research_history"].append({
                "task_id": task.task_id,
                "prompt": task.prompt,
                "result": result
            })

            return {
                "success": True,
                "result": result,
                "metadata": {
                    "role": self.name,
                    "task_id": task.task_id
                }
            }

        except Exception as e:
            logger.error(f"Error in researcher execution: {e}")
            return {
                "success": False,
                "result": "",
                "error": str(e),
                "metadata": {
                    "role": self.name,
                    "task_id": task.task_id
                }
            }

    async def get_state(self) -> Dict[str, Any]:
        return self.state.copy()

    async def restore_state(self, state: Dict[str, Any]):
        self.state = state
        logger.info(f"Restored state for {self.name}")
