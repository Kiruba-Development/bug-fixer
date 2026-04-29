from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage

llm = ChatOllama(model="mistral", temperature=0)
# response = llm.invoke([HumanMessage(content="Reply with this exact JSON: {\"status\": \"ok\"}")])

response = llm.invoke([HumanMessage(content="Translate to French: I love programming.")])
print(response.content)