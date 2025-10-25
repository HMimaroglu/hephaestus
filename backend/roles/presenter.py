import logging
from typing import Dict, Any
from backend.llm import llm_adapter
from backend.schemas import TaskMessage

logger = logging.getLogger(__name__)


class PresenterRole:

    def __init__(self):
        self.name = "presenter"
        self.state: Dict[str, Any] = {
            "presentation_history": [],
            "format_preferences": {}
        }

    async def initialize(self):
        logger.info(f"Initialized {self.name} role")

    async def cleanup(self):
        logger.info(f"Cleaning up {self.name} role")

    async def execute(self, task: TaskMessage) -> dict:
        logger.info(f"Presenter processing task: {task.task_id}")

        system_prompt = """You are a presentation assistant in a distributed AI system.
Your job is to take information and present it in a clear, engaging, and visually appealing way.
Create structured content with headings, bullet points, and clear narratives.
Make complex topics accessible and interesting."""

        try:
            result = await llm_adapter.generate(
                prompt=task.prompt,
                system_prompt=system_prompt,
                temperature=0.8,
                max_tokens=2500
            )

            self.state["presentation_history"].append({
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
            logger.error(f"Error in presenter execution: {e}")
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
