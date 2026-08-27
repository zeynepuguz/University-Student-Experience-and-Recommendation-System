import os

from openai import OpenAI
from dotenv import load_dotenv

from data_collection.vector_store import query_vector_store


load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

ANSWER_MODEL = "gpt-5.6-terra"

SYSTEM_PROMPT = """
Sen UniGuideAI adlı bir üniversite tercih asistanısın. Görevin, gerçek
öğrencilerin YouTube, Ekşi Sözlük ve ŞikayetVar üzerinde paylaştığı
yorumlara dayanarak öğrencilere üniversiteler hakkında dürüst,
kaynaklı cevaplar vermek.

KURALLAR:
- SADECE sana verilen yorum alıntılarına dayanarak cevap ver.
- Yorumlarda yer almayan hiçbir bilgiyi uydurma ya da kendi genel
  bilgeliğinden ekleme.
- Yorumlar arasında çelişki varsa bunu olduğu gibi belirt
  (örn. "bazı öğrenciler ... derken, bazıları ... diyor").
- Verilen yorumlar soruyu cevaplamaya yetmiyorsa bunu açıkça söyle;
  eksik bilgiyi uydurma.
- Cevabın sonunda hangi kaynaklardan (YouTube, Ekşi Sözlük, ŞikayetVar)
  yararlandığını kısaca belirt.
- Türkçe, samimi ama bilgilendirici bir dille yaz.
""".strip()


def build_context(results):
    """
    Chroma sorgu sonucundan LLM'e verilecek numaralı context
    metnini oluşturur.
    """

    documents = results["documents"][0]
    metadatas = results["metadatas"][0]

    context_parts = []

    for index, (document, metadata) in enumerate(
        zip(documents, metadatas),
        start=1
    ):

        context_parts.append(
            f"[{index}] Üniversite: {metadata.get('university_name')} "
            f"| Kaynak: {metadata.get('source')}\n"
            f"{document}"
        )

    return "\n\n".join(context_parts)


def ask(question, university_name=None, n_results=8):
    """
    Kullanıcı sorusunu, vector store'dan getirilen ilgili öğrenci
    yorumlarına dayanarak cevaplar.
    """

    results = query_vector_store(
        question,
        university_name=university_name,
        n_results=n_results
    )

    if not results["documents"][0]:
        return "Bu konuda elimde yeterli yorum bulunmuyor."

    context = build_context(results)

    response = client.chat.completions.create(
        model=ANSWER_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Soru: {question}\n\n"
                    f"Aşağıda ilgili öğrenci yorumları var:\n\n"
                    f"{context}"
                )
            }
        ]
    )

    return response.choices[0].message.content


COMPARE_SYSTEM_PROMPT = """
Sen UniGuideAI adlı bir üniversite tercih asistanısın. Görevin, gerçek
öğrencilerin YouTube, Ekşi Sözlük ve ŞikayetVar üzerinde paylaştığı
yorumlara dayanarak öğrenciye iki üniversiteyi karşılaştırmalı olarak
anlatmak ve öğrencinin kendi önceliklerine göre karar vermesine
yardımcı olmak.

KURALLAR:
- SADECE sana verilen yorum alıntılarına dayanarak konuş.
- Yorumlarda yer almayan hiçbir bilgiyi uydurma.
- Her üniversite için ayrı ayrı, o üniversiteye ait yorumlara dayanarak
  değerlendirme yap; iki üniversiteyi birbirine karıştırma.
- Bir üniversite için yeterli yorum yoksa bunu açıkça söyle.
- Öğrencinin belirttiği önceliğe (soru) göre hangi üniversitenin daha
  uygun görünebileceğini yorumla, ama kesin bir "kazanan" ilan etmek
  yerine gerekçeli bir değerlendirme sun; tercih nihayetinde öğrenciye ait.
- Cevabın sonunda hangi kaynaklardan yararlandığını kısaca belirt.
- Türkçe, samimi ama bilgilendirici bir dille yaz.
""".strip()


def compare(question, university_names, n_results_per_university=6):
    """
    Verilen üniversiteleri, öğrencinin sorusu/önceliği ışığında
    toplanan yorumlara dayanarak karşılaştırır.
    """

    sections = []

    for university_name in university_names:

        results = query_vector_store(
            question,
            university_name=university_name,
            n_results=n_results_per_university
        )

        if results["documents"][0]:
            section_body = build_context(results)
        else:
            section_body = "(Bu üniversite için ilgili yorum bulunamadı.)"

        sections.append(f"=== {university_name} ===\n{section_body}")

    context = "\n\n".join(sections)

    response = client.chat.completions.create(
        model=ANSWER_MODEL,
        messages=[
            {"role": "system", "content": COMPARE_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Öğrencinin sorusu/önceliği: {question}\n\n"
                    f"Karşılaştırılacak üniversiteler:\n\n{context}"
                )
            }
        ]
    )

    return response.choices[0].message.content


def test_ask():

    question = "Kırklareli Üniversitesi'nde sosyal hayat ve ulaşım nasıl?"

    print("\n" + "=" * 60)
    print(f"SORU: {question}")
    print("=" * 60)

    answer = ask(question, university_name="Kırklareli Üniversitesi")

    print(f"\n{answer}")


if __name__ == "__main__":
    test_ask()
