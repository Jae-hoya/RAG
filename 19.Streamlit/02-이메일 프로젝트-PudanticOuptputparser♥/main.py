import os
from dotenv import load_dotenv
import streamlit as st
from langchain_core.messages.chat import ChatMessage
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from langchain_teddynote.prompts import load_prompt
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.output_parsers import PydanticOutputParser
from langchain_community.utilities import SerpAPIWrapper

# API KEY 정보로드
load_dotenv()
# 검색을 위한 api_key
os.environ["SERPAPI_API_KEY"] = (
    "9020cdf9235a65b087f324a802b283ff67ac56cf8ddf0ab5bc8522c284d4a573"
)

st.title("Email 요약기💬")


# 처음 1번만 실행하기 위한 코드
if "messages" not in st.session_state:
    # 대화기록을 저장하기 위한 용도로 생성한다.
    st.session_state["messages"] = []

# 사이드바 생성
with st.sidebar:
    # 초기화 버튼 생성
    clear_btn = st.button("대화 초기화")


# 이전 대화를 출력
def print_messages():
    for chat_message in st.session_state["messages"]:
        st.chat_message(chat_message.role).write(chat_message.content)


# 새로운 메시지를 추가
def add_message(role, message):
    st.session_state["messages"].append(ChatMessage(role=role, content=message))


# pydantic. 이메일 본문에서 주요 엔티티 추출
class EmailSummary(BaseModel):
    person: str = Field(description="메일을 보낸 사람")
    email: str = Field(description="메일을 보낸 사람의 이메일 주소")
    subject: str = Field(description="메일 제목")
    summary: str = Field(description="메일 본문을 요약한 텍스트")
    date: str = Field(description="메일 본문에 언급된 미팅 날짜와 시간")
    company: str = Field(description="메일을 보낸 사람의 회사정보")


# pydantic 체인 생성
def create_email_parsing_chain():

    llm = ChatOpenAI(model="gpt-4o-mini")

    # PydanticOutputParser 생성 - prompt에 get_format_instruction을 넣어주기 위해서.
    output_parser = PydanticOutputParser(pydantic_object=EmailSummary)

    # PROMPT 생성
    template = """
    You are a helpful assistant. Please answer the following questions in KOREAN.

    #Question:
    다음의 이메일 내용 중에서 주요 내용을 추출해 주세요.

    #Email Converation:
    {email_conversation}

    #Format:
    {format}
    """

    prompt = PromptTemplate.from_template(template)
    prompt = prompt.partial(format=output_parser.get_format_instructions())

    chain = prompt | llm | output_parser

    return chain


# 두번째 체인
def create_report_chain():

    llm = ChatOpenAI(model="gpt-4o-mini")

    prompt = load_prompt("prompts/email.yaml", encoding="utf-8")

    # 출력 파서
    output_parser = StrOutputParser()

    # 체인 생성
    chain = prompt | llm | output_parser
    return chain


# 초기화 버튼이 눌리면...
if clear_btn:
    st.session_state["messages"] = []

# 이전 대화 기록 출력
print_messages()

# 사용자의 입력
user_input = st.chat_input("궁금한 내용을 물어보세요!")

# 만약에 사용자 입력이 들어오면...
if user_input:
    # 사용자의 입력
    st.chat_message("user").write(user_input)

    # 1)email을 파싱하는 chain 을 생성 및 실행
    email_chain = create_email_parsing_chain()
    # email에서 주요 정보를 추출하는 체인
    answer = email_chain.invoke({"email_conversation": user_input})

    # 2) 보낸 사람의 추가 정보 수집(검색)
    params = {
        "engine": "google",
        "gl": "kr",
        "hl": "ko",
        "num": "3",
    }  # 검색 파라미터 hl은 google ui language, gl은 country
    search = SerpAPIWrapper(params=params)  # 검색 객체
    search_query = f"{answer.person} {answer.company} {answer.email}"  # 검색 query
    search_result = search.run(search_query)  # 검색 query실행
    search_result = eval(search_result)  # 리스트 형태로 반환
    search_result_string = "\n".join(
        search_result
    )  # 검색 결과를 스트링으로 만들어준다.

    # 3) 이메일 요약 리포트 생성. 검색한 결과를 가지고 정리를 해준다.
    report_chain = create_report_chain()
    report_chain_input = {
        "sender": answer.person,
        "additional_information": search_result_string,
        "company": answer.company,
        "email": answer.email,
        "subject": answer.subject,
        "summary": answer.summary,
        "date": answer.date,
    }

    # 스트리밍 호출
    response = report_chain.stream(report_chain_input)
    with st.chat_message("assistant"):
        # 빈 공간(컨테이너)을 만들어서, 여기에 토큰을 스트리밍 출력한다.
        container = st.empty()

        ai_answer = ""
        for token in response:
            ai_answer += token
            container.markdown(ai_answer)

    # 대화기록을 저장한다.
    add_message("user", user_input)
    add_message("assistant", ai_answer)

# streamlit run .\main.py
