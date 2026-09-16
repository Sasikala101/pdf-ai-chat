from langchain_core.messages import AIMessage


def test_structured_gemini_content_exposes_plain_text() -> None:
    response = AIMessage(
        content=[
            {
                "type": "text",
                "text": "Summary:\n\n* **Experience:** Five years [Page 1].",
                "extras": {"signature": "private-provider-metadata"},
            }
        ]
    )

    answer = str(response.text).strip()

    assert answer.startswith("Summary:")
    assert "**Experience:**" in answer
    assert "signature" not in answer
