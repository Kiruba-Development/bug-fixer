# import getpass
# import os
# from dotenv import load_dotenv

# load_dotenv()
# if "GEMINI_API_KEY" not in os.environ:
#     os.environ["GEMINI_API_KEY"] = getpass.getpass("Enter your Gemini API key: ")


# # Replace ChatGroq with this in all 3 agent files
# from langchain_google_genai import ChatGoogleGenerativeAI

# llm = ChatGoogleGenerativeAI(
#     model="gemini-2.0-flash",
#     temperature=0
# )

# result = llm.invoke("Translate to French: I love programming.")
# print(result.content)
















# # os.environ["LANGSMITH_API_KEY"] = getpass.getpass("Enter your LangSmith API key: ")
# # os.environ["LANGSMITH_TRACING"] = "true"


# # from langchain_groq import ChatGroq
# # from tools.retry_utils import invoke_with_retry

# # llm = ChatGroq(
# #     model="qwen/qwen3-32b",
# #     temperature=0,
# #     max_tokens=None,
# #     timeout=None,
# #     max_retries=2,
# #     # other params...
# # )

# # messages = [
# #     (
# #         "system",
# #         "You are a helpful assistant that translates English to French. Translate the user sentence.",
# #     ),
# #     ("human", "I love programming."),
# # ]
# # ai_msg = llm.invoke(messages)
# # print(ai_msg.content)