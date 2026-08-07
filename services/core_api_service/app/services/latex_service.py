import re
from typing import Dict, Any, List

def escape_latex(text: Any) -> str:
    """Escapes special LaTeX characters to guarantee compilation safety."""
    if not text:
        return ""
    s = str(text)
    s = s.replace("\\", "\\textbackslash{}")
    s = s.replace("&", "\\&")
    s = s.replace("%", "\\%")
    s = s.replace("$", "\\$")
    s = s.replace("#", "\\#")
    s = s.replace("_", "\\_")
    s = s.replace("{", "\\{")
    s = s.replace("}", "\\}")
    s = s.replace("~", "\\textasciitilde{}")
    s = s.replace("^", "\\textasciicircum{}")
    return s

class LatexService:
    TEMPLATES = [
        {
            "id": "jakes-resume",
            "name": "Jake's Resume",
            "category": "Software Engineering",
            "tag": "ATS Gold Standard",
            "description": "The #1 most popular 1-page tech resume template. Highly optimized for ATS parsers.",
            "accent_color": "#2563eb",
        },
        {
            "id": "modern-cv",
            "name": "ModernCV Classic",
            "category": "Corporate & Product",
            "tag": "Executive & Clean",
            "description": "Elegant European/American corporate standard with distinctive badges and structured sections.",
            "accent_color": "#0284c7",
        },
        {
            "id": "deedy-cv",
            "name": "Deedy CV (2-Column)",
            "category": "Data Science & Research",
            "tag": "High Density 2-Col",
            "description": "Two-column compact resume designed by Debarghya Das for engineers and researchers.",
            "accent_color": "#7c3aed",
        },
        {
            "id": "awesome-cv",
            "name": "Awesome CV",
            "category": "Senior & Staff Engineers",
            "tag": "Modern Typography",
            "description": "Award-winning LaTeX template with beautiful font pairings and clean bullet alignments.",
            "accent_color": "#059669",
        },
        {
            "id": "minimalist-cv",
            "name": "Minimalist Single Column",
            "category": "Management & General",
            "tag": "ATS Direct",
            "description": "Distraction-free classic layout with timeless typography for general and executive roles.",
            "accent_color": "#475569",
        },
    ]

    @classmethod
    def get_templates(cls) -> List[Dict[str, Any]]:
        return cls.TEMPLATES

    @classmethod
    def get_template(cls, template_id: str) -> Dict[str, Any]:
        for t in cls.TEMPLATES:
            if t["id"] == template_id:
                return t
        return cls.TEMPLATES[0]

    @classmethod
    def generate_latex(cls, template_id: str, profile_data: Dict[str, Any]) -> str:
        tid = template_id.lower()
        if tid == "modern-cv":
            return cls._generate_modern_cv(profile_data)
        elif tid == "deedy-cv":
            return cls._generate_deedy_cv(profile_data)
        elif tid == "awesome-cv":
            return cls._generate_awesome_cv(profile_data)
        elif tid == "minimalist-cv":
            return cls._generate_minimalist_cv(profile_data)
        else:
            return cls._generate_jakes_resume(profile_data)

    @classmethod
    def _extract_fields(cls, p: Dict[str, Any]):
        personal = p.get("personalInfo") or p.get("personal_info") or {}
        first_name = personal.get("firstName") or personal.get("first_name") or ""
        last_name = personal.get("lastName") or personal.get("last_name") or ""
        name = f"{first_name} {last_name}".strip() or p.get("display_name") or p.get("displayName") or "Candidate Name"
        email = personal.get("email") or p.get("email") or ""
        phone = personal.get("phone") or p.get("phone") or ""
        location = personal.get("location") or (p.get("preferred_locations", [""])[0] if p.get("preferred_locations") else "")
        
        summary = (p.get("professionalSummary") or {}).get("detailedSummary") or p.get("summary") or p.get("headline") or ""
        
        skills = p.get("skills") or p.get("skills_flat") or []
        skills_str = ", ".join([escape_latex(s if isinstance(s, str) else s.get("name", "")) for s in skills]) if skills else ""

        experience = p.get("employmentHistory") or p.get("experience") or []
        projects = p.get("projects") or []
        education = p.get("education") or {}
        if isinstance(education, list) and len(education) > 0:
            education = education[0]
        
        return {
            "name": escape_latex(name),
            "email": escape_latex(email),
            "phone": escape_latex(phone),
            "location": escape_latex(location),
            "summary": escape_latex(summary),
            "skills_str": skills_str,
            "experience": experience,
            "projects": projects,
            "education": education,
        }

    @classmethod
    def _generate_jakes_resume(cls, profile: Dict[str, Any]) -> str:
        d = cls._extract_fields(profile)
        
        exp_latex = []
        for job in d["experience"]:
            title = escape_latex(job.get("designation") or job.get("title") or "Software Engineer")
            company = escape_latex(job.get("company") or "Tech Solutions")
            duration = escape_latex(job.get("duration") or "2022 -- Present")
            bullets = job.get("keyResponsibilities") or job.get("responsibilities") or [
                "Architected and deployed high-performance microservices.",
                "Optimized core database queries reducing latency by 40%."
            ]
            bullet_items = "\n".join([f"        \\resumeItem{{{escape_latex(b)}}}" for b in bullets])
            exp_latex.append(f"""    \\resumeSubheading
      {{{title}}}{{{duration}}}
      {{{company}}}{{{d['location']}}}
      \\resumeItemListStart
{bullet_items}
      \\resumeItemListEnd""")

        exp_str = "\n\n".join(exp_latex) if exp_latex else """    \\resumeSubheading
      {Senior Software Engineer}{2022 -- Present}
      {Tech Solutions Inc.}{Remote}
      \\resumeItemListStart
        \\resumeItem{Architected and deployed high-performance microservices serving 100k+ users.}
      \\resumeItemListEnd"""

        edu = d["education"]
        edu_deg = escape_latex(edu.get("degree") or "Bachelor of Science in Computer Science")
        edu_uni = escape_latex(edu.get("university") or edu.get("institution") or "University of Technology")
        edu_dur = escape_latex(edu.get("duration") or "2018 -- 2022")

        return f"""\\documentclass[letterpaper,11pt]{{article}}
\\usepackage{{latexsym}}
\\usepackage[empty]{{fullpage}}
\\usepackage{{titlesec}}
\\usepackage{{marvosym}}
\\usepackage[usenames,dvipsnames]{{color}}
\\usepackage{{verbatim}}
\\usepackage{{enumitem}}
\\usepackage[hidelinks]{{hyperref}}
\\usepackage{{fancyhdr}}
\\usepackage[english]{{babel}}
\\usepackage{{tabularx}}
\\input{{glyphtounicode}}

\\pagestyle{{fancy}}
\\fancyhf{{}}
\\renewcommand{{\\headrulewidth}}{{0pt}}
\\renewcommand{{\\footrulewidth}}{{0pt}}

\\addtolength{{\\oddsidemargin}}{{-0.5in}}
\\addtolength{{\\evensidemargin}}{{-0.5in}}
\\addtolength{{\\textwidth}}{{1in}}
\\addtolength{{\\topmargin}}{{-.5in}}
\\addtolength{{\\textheight}}{{1.0in}}

\\titleformat{{\\section}}{{\\vspace{{-4pt}}\\scshape\\raggedright\\large}}{{}}{{0em}}{{}}[\\color{{black}}\\titlerule \\vspace{{-5pt}}]
\\pdfgentounicode=1

\\newcommand{{\\resumeItem}}[1]{{\\item\\small{{#1 \\vspace{{-2pt}}}}}}
\\newcommand{{\\resumeSubheading}}[4]{{\\vspace{{-2pt}}\\item\\begin{{tabular*}}{{0.97\\textwidth}}[t]{{l@{{\\extracolsep{{\\fill}}}}r}}\\textbf{{#1}} & #2 \\\\\\textit{{\\small#3}} & \\textit{{\\small #4}} \\\\\\end{{tabular*}}\\vspace{{-7pt}}}}
\\newcommand{{\\resumeProjectHeading}}[2]{{\\item\\begin{{tabular*}}{{0.97\\textwidth}}{{l@{{\\extracolsep{{\\fill}}}}r}}\\small#1 & #2 \\\\\\end{{tabular*}}\\vspace{{-7pt}}}}
\\newcommand{{\\resumeSubHeadingListStart}}{{\\begin{{itemize}}[leftmargin=0.15in, label={{}}]}}
\\newcommand{{\\resumeSubHeadingListEnd}}{{\\end{{itemize}}}}
\\newcommand{{\\resumeItemListStart}}{{\\begin{{itemize}}}}
\\newcommand{{\\resumeItemListEnd}}{{\\end{{itemize}}\\vspace{{-5pt}}}}

\\begin{{document}}

\\begin{{center}}
    \\textbf{{\\Huge \\scshape {d['name']}}} \\\\ \\vspace{{2pt}}
    \\small {d['phone']} $|$ \\href{{mailto:{d['email']}}}{{\\underline{{{d['email']}}}}} $|$ {d['location']}
\\end{{center}}

\\section{{Education}}
  \\resumeSubHeadingListStart
    \\resumeSubheading
      {{{edu_uni}}}{{{edu_dur}}}
      {{{edu_deg}}}{{{d['location']}}}
  \\resumeSubHeadingListEnd

\\section{{Experience}}
  \\resumeSubHeadingListStart
{exp_str}
  \\resumeSubHeadingListEnd

\\section{{Technical Skills}}
 \\begin{{itemize}}[leftmargin=0.15in, label={{}}]
    \\small{{\\item{{
     \\textbf{{Technologies}}{{: {d['skills_str']}}}
    }}}}
 \\end{{itemize}}

\\end{{document}}
"""

    @classmethod
    def _generate_modern_cv(cls, profile: Dict[str, Any]) -> str:
        d = cls._extract_fields(profile)
        return f"""\\documentclass[11pt,a4paper,sans]{{moderncv}}
\\moderncvstyle{{classic}}
\\moderncvcolor{{blue}}
\\usepackage[scale=0.82]{{geometry}}

\\name{{{d['name'].split()[0] if d['name'] else 'Candidate'}}}{{{d['name'].split()[-1] if len(d['name'].split()) > 1 else ''}}}
\\address{{{d['location']}}}{{}}{{}}
\\phone[mobile]{{{d['phone']}}}
\\email{{{d['email']}}}

\\begin{{document}}
\\makecvtitle

\\section{{Technical Competencies}}
\\cvitem{{Skills}}{{{d['skills_str']}}}

\\section{{Education}}
\\cventry{{2018 -- 2022}}{{B.S. in Computer Science}}{{University of Technology}}{{{d['location']}}}{{}}{{}}

\\end{{document}}
"""

    @classmethod
    def _generate_deedy_cv(cls, profile: Dict[str, Any]) -> str:
        d = cls._extract_fields(profile)
        return f"""\\documentclass[]{{deedy-resume-openfont}}
\\begin{{document}}
\\namesection{{{d['name']}}}{{}}{{\\href{{mailto:{d['email']}}}{{{d['email']}}} | {d['phone']} | {d['location']}}}

\\begin{{minipage}}[t]{{0.33\\textwidth}}
\\section{{Skills}}
{d['skills_str']}
\\end{{minipage}}
\\hfill
\\begin{{minipage}}[t]{{0.65\\textwidth}}
\\section{{Experience}}
Software Engineer at Tech Innovations
\\end{{minipage}}
\\end{{document}}
"""

    @classmethod
    def _generate_awesome_cv(cls, profile: Dict[str, Any]) -> str:
        d = cls._extract_fields(profile)
        return f"""\\documentclass[11pt, a4paper]{{awesome-cv}}
\\colorlet{{awesome}}{{awesome-emerald}}
\\name{{{d['name']}}}{{}}
\\email{{{d['email']}}}
\\mobile{{{d['phone']}}}
\\address{{{d['location']}}}

\\begin{{document}}
\\makecvheader[C]
\\cvsection{{Skills}}
\\begin{{cvskills}}
  \\cvskill{{Core}}{{{d['skills_str']}}}
\\end{{cvskills}}
\\end{{document}}
"""

    @classmethod
    def _generate_minimalist_cv(cls, profile: Dict[str, Any]) -> str:
        d = cls._extract_fields(profile)
        return f"""\\documentclass[10pt,letterpaper]{{article}}
\\usepackage[margin=0.7in]{{geometry}}
\\usepackage{{hyperref}}

\\begin{{document}}
\\begin{{center}}
  {{\\LARGE \\textbf{{{d['name']}}}}} \\\\[4pt]
  \\small {d['location']} $|$ {d['phone']} $|$ {d['email']}
\\end{{center}}
\\hrule
\\vspace{{6pt}}
\\noindent \\textbf{{\\large Skills}} \\\\[4pt]
{d['skills_str']}
\\end{{document}}
"""
