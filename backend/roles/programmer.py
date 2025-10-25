import logging
from typing import Dict, Any
from backend.llm import llm_adapter
from backend.schemas import TaskMessage

logger = logging.getLogger(__name__)


class ProgrammerRole:

    def __init__(self):
        self.name = "programmer"
        self.state: Dict[str, Any] = {
            "code_history": [],
            "language_stats": {}
        }

    async def initialize(self):
        logger.info(f"Initialized {self.name} role")

    async def cleanup(self):
        logger.info(f"Cleaning up {self.name} role")

    async def execute(self, task: TaskMessage) -> dict:
        logger.info(f"Programmer processing task: {task.task_id}")

        system_prompt = """You are a programming assistant in a distributed AI system.
Your job is to write clean, efficient, and well-documented code.
Follow best practices, include error handling, and explain your implementation choices.
Always format code properly with appropriate syntax highlighting."""

        try:
            result = await llm_adapter.generate(
                prompt=task.prompt,
                system_prompt=system_prompt,
                temperature=0.3,
                max_tokens=3000
            )

            self.state["code_history"].append({
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
            logger.error(f"Error in programmer execution: {e}")
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
