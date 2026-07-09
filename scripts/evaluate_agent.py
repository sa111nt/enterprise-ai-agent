import asyncio
import os
import sys

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agent.graph import get_graph, initialize_graph, shutdown_graph


class EvaluationResult(BaseModel):
    is_correct: bool = Field(
        description="Whether the agent's answer accurately addresses the question based on the expected behavior"
    )
    reasoning: str = Field(
        description="Explanation of why the answer is correct or incorrect"
    )
    correct_tools_used: bool = Field(
        description="Whether the expected tools were called by the agent"
    )


DATASET = [
    {
        "question": "What is my onboarding status?",
        "expected_tool": "onboarding_status",
        "expected_answer_properties": "Should inform the user about pending or completed tasks.",
    },
    {
        "question": "Who is John Doe?",
        "expected_tool": "employee_lookup",
        "expected_answer_properties": "Should mention John's role, department, and contact info.",
    },
    {
        "question": "What is our work from home policy?",
        "expected_tool": "search_regulations",
        "expected_answer_properties": "Should cite the HR policy document regarding remote work.",
    },
]


async def evaluate():
    load_dotenv()

    print("Initializing agent graph...")
    await initialize_graph()
    graph = get_graph()

    judge_llm = ChatOpenAI(model="gpt-4o", temperature=0).with_structured_output(
        EvaluationResult
    )

    results = []

    # Dummy employee context for testing
    config = {
        "configurable": {
            "thread_id": "eval_thread_123",
            "employee_id": 1,
            "employee_role": "admin",
        }
    }

    try:
        for idx, item in enumerate(DATASET):
            print(f"\nEvaluating Question {idx+1}: {item['question']}")

            input_msg = {"messages": [HumanMessage(content=item["question"])]}

            # Run the agent
            events = graph.astream_events(input_msg, config, version="v2")

            tools_called = set()
            final_answer = ""

            async for event in events:
                kind = event["event"]
                if kind == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    if chunk.content:
                        final_answer += chunk.content
                elif kind == "on_tool_start":
                    tools_called.add(event.get("name", ""))

            print(f"Tools Called: {tools_called}")
            print(f"Agent Answer: {final_answer}")

            # Judge the output
            judge_prompt = f"""
            You are an impartial judge evaluating an AI HR assistant.
            Question asked: {item['question']}
            Expected Answer Properties: {item['expected_answer_properties']}
            Expected Tool to be used: {item['expected_tool']}
            
            Agent's Answer: {final_answer}
            Tools actually used by Agent: {tools_called}
            
            Evaluate if the agent's answer is correct and if it used the expected tool.
            """

            evaluation: EvaluationResult = await judge_llm.ainvoke(
                [HumanMessage(content=judge_prompt)]
            )

            print(f"Evaluation Correct: {evaluation.is_correct}")
            print(f"Evaluation Reasoning: {evaluation.reasoning}")

            results.append(evaluation.is_correct and evaluation.correct_tools_used)

        total = len(DATASET)
        passed = sum(1 for r in results if r)
        print("\n--- Evaluation Summary ---")
        print(f"Passed: {passed}/{total}")

    finally:
        await shutdown_graph()


if __name__ == "__main__":
    asyncio.run(evaluate())
