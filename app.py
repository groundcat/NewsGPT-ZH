import sys
import requests
from bs4 import BeautifulSoup
import openai
import streamlit as st
from datetime import datetime
import deepl
from dotenv import load_dotenv
import os

# Load environment variables from .env
load_dotenv()
openai_api_key = str(os.getenv("OPENAI_API_KEY"))
openai.api_key = openai_api_key
deepl_api_key = str(os.getenv("DEEPL_API_KEY"))
mastodon_api_url = str(os.getenv("MASTODON_API_URL"))
mastodon_api_key = "Bearer " + str(os.getenv("MASTODON_API_KEY"))
max_length = 2000


def deepl_to_zh(text):
    """
    Translate text to Chinese using Deepl API
    :param text:
    :return:
    """

    if deepl_api_key is None or deepl_api_key == "":
        print("Deepl API Key is not set")
        sys.exit(1)

    translator = deepl.Translator(deepl_api_key)
    result = str(translator.translate_text(text, target_lang="ZH"))
    print(f"Translated to Chinese: {result}")
    return result


def get_news_article_content(url):
    """
    Get the news article content and title from the url
    returns a dictionary containing the title and content in text format without any html tags
    :param url:
    :return:
    """

    print(f"Getting news article content from {url}")

    # send a request to the url and get the response
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/58.0.3029.110 Safari/537.3'}
    response = requests.get(url, headers=headers)

    # parse the response using BeautifulSoup
    soup = BeautifulSoup(response.content, 'html.parser')
    # find the title of the article
    title = soup.find('h1').text.strip()
    # find the article tag
    article = soup.find('article')
    # find all the paragraphs in the article
    paragraphs = article.find_all('p')
    # concatenate the text in all the paragraphs
    content_text = ''
    for paragraph in paragraphs:
        content_text += paragraph.text.strip()

    # Remove any line changes, duplicate whitespaces, and any other special characters
    content_text = content_text.replace('\n', ' ').replace('\r', '').replace('\t', ' ')

    # Remove any duplicate whitespaces until there is only one whitespace
    while '  ' in content_text:
        content_text = content_text.replace('  ', ' ')

    # When exceed 5000 chars, cut it at the last sentence
    if len(content_text) > 5000:
        content_text = content_text[:5000]
        content_text = content_text[:content_text.rfind('.') + 1]

    return {'title': title, 'content': content_text}


def summarize_news_article_chinese(news_dict):
    """
    Summarize the news article content using OpenAI API
    in Chinese language and then
    returns the summarized content in text format
    :param news_dict:
    :return:
    """

    if openai_api_key is None:
        print("OpenAI API Key is not set")
        sys.exit(1)

    print(f"Summarizing news article content titled {news_dict['title']}")

    title = news_dict['title']
    content = news_dict['content']

    if len(title) < 10 or len(content) < 100:
        return

    # trunc content under 2000 chars
    if len(content) > 1800:
        content = content[:1800]

    # send a request to the OpenAI API to summarize the article content in Chinese
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "system",
                   "content": "你是一名记者，你要为一篇新闻报道写一份新闻简报。"},
                  {"role": "user", "content": f"用中文写一篇新闻简报，将以下新闻文章总结为1-2个正文段落。\n"
                                              f"\n"
                                              f"===\n"
                                              f"原文标题: {title}\n"
                                              f"原文正文: {content}"}]
    )
    print(response)

    # get the summarized content from the response
    summarized_content = str(response.choices[0]['message']['content'])

    # create log folder if not exist
    if not os.path.exists("logs"):
        os.makedirs("logs")

    # create a txt log file to store the summarized content, filename with timestamp
    with open(f"logs/{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.txt", "w") as f:
        f.write(summarized_content)

    return summarized_content


def post_to_mastodon(body):
    """
    Post the body to Mastodon
    :param body:
    :return:
    """
    if mastodon_api_url is None or mastodon_api_key is None:
        print("Mastodon API URL or API Key is not set")
        sys.exit(1)

    form_data = {
        "status": body,
        "visibility": "public",
    }

    response = requests.post(mastodon_api_url, data=form_data, headers={"Authorization": mastodon_api_key})

    print(response.status_code)

    if response.status_code != 200:
        print(f"Error code: {response.status_code}")
        sys.exit(1)

    print("Success")


def create_post_text(body, url):
    """
    Keep the body + url within the max length, while keeping the full url
    :param body:
    :param url:
    :return:
    """
    if len(body) + len(url) > max_length:
        body = body[:max_length - len(url) - 3] + "..."
    return body + "\n" + url


def main():
    st.title("NewsGPT-ZH")
    st.write("Translate, summarize, and publish news articles using DeepL and OpenAI GPT-3")

    # Input box for URL
    url = st.text_input("Enter the URL of the news article:")

    summary = ""

    # Publish and Fetch Article buttons
    col1, col2 = st.columns(2)
    if col1.button("Summarize Article"):
        if url == "" or not url.startswith("http"):
            st.error("Invalid URL")
        else:
            news_dict = get_news_article_content(url)

            title = deepl_to_zh(news_dict['title'])
            content = deepl_to_zh(news_dict['content'])

            # If too short, skip it
            if len(title) < 10 or len(content) < 100:
                st.warning("Article is too short")
            else:
                summary = summarize_news_article_chinese(news_dict)
                # update the Summarized content text area
                st.text_area("Summary", summary)

    if col2.button("Publish to Mastodon"):
        summary = st.text_area("Summary", summary)
        post_content = create_post_text(summary, url)
        post_to_mastodon(str(post_content))
        st.success("Published to Mastodon!")


if __name__ == '__main__':
    main()
