from pathlib import Path

from docx import Document


def main():
    destination = Path(__file__).parent / "fixtures" / "asha-rao-resume.docx"
    destination.parent.mkdir(exist_ok=True)
    document = Document()
    for line in [
        "Name: Asha Rao",
        "Email: asha.candidate@example.com",
        "+919876543210",
        "Role: Senior Backend Engineer",
        "Company: SignalWorks",
        "Location: Bengaluru",
        "6 years of experience",
        "Skills: Python, Django, PostgreSQL, Kafka, AWS",
        "https://linkedin.com/in/asharao",
        "https://github.com/asharao",
        "Notice period: 30 days",
        "Current salary: 22.5",
        "Expected salary: 28",
        "Summary: Builds reliable event-driven platforms for high-volume products.",
        "Experience: Senior Backend Engineer|SignalWorks|2022-01-01|Present|"
        "Owned payments APIs and Kafka consumers",
        "Experience: Software Engineer|EarlyStack|2019-01-01|2021-08-01|Built Django services",
        "Education: B.Tech Computer Science, PES University",
    ]:
        document.add_paragraph(line)
    document.save(destination)
    print(destination)


if __name__ == "__main__":
    main()
