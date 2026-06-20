from dotenv import load_dotenv
from langchain_huggingface import HuggingFaceEmbeddings, ChatHuggingFace, HuggingFaceEndpoint
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda

load_dotenv()

llm = HuggingFaceEndpoint(
    repo_id="meta-llama/Meta-Llama-3-8B-Instruct",
    task="text-generation",
)

model = ChatHuggingFace(llm=llm)
# class DebugReport(BaseModel):
#     explanation: str = Field(description = "Explanation about the error in the terminal")


# parser = parser = PydanticOutputParser(pydantic_object=DebugReport)
parser = StrOutputParser
template = PromptTemplate.from_template(
    template=""""
        Describe {name} in 10 words
    """
)

#, partial_variables={"format_instructions": parser.get_format_instructions()}
usage_data = None

def get_token_data(response):
    global usage_data
    usage_data = response.usage_metadata
    return response

chain = template | model | RunnableLambda(get_token_data) | parser
output = chain.invoke({"name": "Virat Kohli"})

# also display actual error text using dim incase model hallucinates
print(output)
