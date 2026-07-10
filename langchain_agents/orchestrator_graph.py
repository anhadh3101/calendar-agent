from langgraph.graph import StateGraph, START, END
from typing_extensions import TypedDict

class MyGraphState(TypedDict): 
    count: int
    msg: str
    
def counter(state: MyGraphState):
  state["count"] += 1
  state["msg"] = f"Counter function has been called {state['count']} time(s)"
  return state

workflow = StateGraph(MyGraphState)

workflow.add_node("node1", counter)
workflow.add_node("node2", counter)
workflow.add_node("node3", counter)

workflow.add_edge(START, "node1")
workflow.add_edge("node1", "node2")
workflow.add_edge("node2", "node3")
workflow.add_edge("node3", END)

app = workflow.compile()

print(app.invoke({ "count": 0, "msg": "hello" }))

