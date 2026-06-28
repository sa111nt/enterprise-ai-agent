from typing import Annotated

from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages
from typing_extensions import TypedDict


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
