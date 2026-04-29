from django.http import HttpResponse, JsonResponse
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from io import BytesIO
from .models import UserProfile
from .services import generate_letter
import json
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
import os
from django.shortcuts import render
import re
from django.core.files.base import ContentFile
from .models import UserProfile, GeneratedLetter

def home(request):
    return render(request, "core/index.html")

# SAVE PROFILE API
def save_profile(request):
    if request.method == "POST":
        # support both JSON and form-data
        if request.content_type == "application/json":
            data = json.loads(request.body)
            signature_file = None
        else:
            data = request.POST
            signature_file = request.FILES.get("signature")

        profile, created = UserProfile.objects.update_or_create(
            tin=data.get("tin"),
            defaults={
                "email": data.get("email"),
                "name": data.get("name"),
                "phone": data.get("phone"),
                "signature": signature_file
            }
        )

        return JsonResponse({
            "message": "Profile saved",
            "created": created
        })

    return JsonResponse({"error": "Invalid request method"}, status=400)


# GENERATE LETTER PDF API
def generate_letter_api(request):
    if request.method == "POST":

        # Handle form-data vs JSON
        if request.content_type.startswith('multipart/form-data'):
            data = request.POST
            signature_file = request.FILES.get("signature")
        else:
            data = json.loads(request.body)
            signature_file = None

        tin = data.get("tin", "")
        email = data.get("email", "")
        name = data.get("name", "")

        # ✅ VALIDATION
        if not re.fullmatch(r"1\d{8}", tin):
            return JsonResponse({
                "error": "Wrong TIN"
            }, status=400)

        if name and not re.fullmatch(r"[A-Za-z0-9 ]{2,30}", name):
            return JsonResponse({
                "error": "Name must be 2–30 characters (letters/numbers only)"
            }, status=400)

        # ✅ CREATE / UPDATE PROFILE (ONLY ONCE)
        profile, _ = UserProfile.objects.update_or_create(
            tin=tin,
            defaults={
                "email": email,
                "name": name,
                "phone": data.get("phone"),
                "signature": signature_file
            }
        )

        language = data.get("language", "en")
        months = data.get("months")
        initial_payment = data.get("initial_payment")

        # Generate letter text
        letter_text = generate_letter(
            profile,
            language=language,
            months=months,
            initial_payment=initial_payment
        )

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer)
        styles = getSampleStyleSheet()

        normal = styles["Normal"]

        bold = ParagraphStyle(
            name="Bold",
            parent=styles["Normal"],
            fontName="Helvetica-Bold"
        )

        right_style = ParagraphStyle(
            name="Right",
            parent=styles["Normal"],
            alignment=TA_RIGHT
        )

        signature_style = ParagraphStyle(
            name="Signature",
            parent=styles["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=14
        )

        # Extract date
        lines = letter_text.splitlines()
        date_line = [l for l in lines if "Date:" in l][0]

        # HEADER
        header_table = Table([
            [
                Paragraph(
                    f"{profile.name}<br/>TIN: {profile.tin}<br/>Tel: {profile.phone}<br/>Email: {profile.email}",
                    normal
                ),
                Paragraph(f"{date_line}", right_style)
            ]
        ], colWidths=[300, 200])

        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP')
        ]))

        content = []
        content.append(header_table)
        content.append(Spacer(1, 25))

        # Recipient + Subject
        if language == "rw":
            content.append(Paragraph(
                "Komiseri Wungirije ushinzwe gucunga ibirarane<br/>KIGALI",
                normal
            ))
            content.append(Spacer(1, 15))

            content.append(Paragraph(
                "<b>Impamvu: gusaba kwishyura mu byiciro</b>",
                bold
            ))
            content.append(Spacer(1, 15))

            content.append(Paragraph("Nyakubahwa Komiseri,", normal))
        else:
            content.append(Paragraph(
                "To: Deputy Commissioner in charge of Arrears Management<br/>KIGALI",
                normal
            ))
            content.append(Spacer(1, 15))

            content.append(Paragraph(
                "<b>Subject: Request for installment payment</b>",
                bold
            ))
            content.append(Spacer(1, 15))

            content.append(Paragraph("Dear Sir/Madam,", normal))

        content.append(Spacer(1, 15))

        # BODY
        if language == "rw":
            content.append(Paragraph(
                f"Nanditse nsaba kwishyura mu byiciro umusoro mbereyemo RRA. "
                f"Nkaba nifuza kwishyura uwo musoro mu {months}.",
                normal
            ))
            content.append(Spacer(1, 10))

            content.append(Paragraph(
                f"Nkuko nabisabwe, nkaba nishyuye icyiciro cya mbere kingana na {initial_payment}.",
                normal
            ))
            content.append(Spacer(1, 10))

            content.append(Paragraph(
                "Mu gihe ngitegereje igisubizo cyanyu cyiza mbaye mbashimiye.",
                normal
            ))
        else:
            content.append(Paragraph(
                "I am writing to request permission to pay my outstanding tax liabilities in installments.",
                normal
            ))
            content.append(Spacer(1, 10))

            content.append(Paragraph(
                f"I propose to settle the amount over a period of {months} months.",
                normal
            ))
            content.append(Spacer(1, 10))

            content.append(Paragraph(
                f"As required, I have already made an initial payment of {initial_payment}.",
                normal
            ))
            content.append(Spacer(1, 10))

            content.append(Paragraph(
                "While awaiting your positive response, I thank you in advance.",
                normal
            ))

        content.append(Spacer(1, 30))

        # Closing
        if language == "rw":
            content.append(Paragraph("Murakoze.", normal))
        else:
            content.append(Paragraph("Yours faithfully,", normal))

        content.append(Spacer(1, 20))

        # SIGNATURE
        if profile.signature and hasattr(profile.signature, 'path') and os.path.exists(profile.signature.path):
            content.append(Image(profile.signature.path, width=120, height=50))
            content.append(Spacer(1, 10))
            content.append(Paragraph(profile.name, bold))
        else:
            content.append(Paragraph(profile.name, signature_style))

        doc.build(content)

        buffer.seek(0)

        # ✅ SAVE PDF TO DATABASE
        file_name = f"letter_{profile.tin}.pdf"
        pdf_file = ContentFile(buffer.getvalue(), name=file_name)

        GeneratedLetter.objects.create(
            profile=profile,
            file=pdf_file
        )

        # Return file
        return HttpResponse(
            buffer,
            content_type="application/pdf",
            headers={
                "Content-Disposition": "attachment; filename=letter.pdf"
            },
        )

    return JsonResponse({"error": "Invalid request method"}, status=400)

def my_letters(request):
    letters = []
    tin = None
    error = None

    if request.method == "POST":
        tin = request.POST.get("tin")

        try:
            profile = UserProfile.objects.get(tin=tin)
            letters = GeneratedLetter.objects.filter(profile=profile).order_by('-created_at')
        except UserProfile.DoesNotExist:
            error = "No user found with this TIN"

    return render(request, "core/my_letters.html", {
        "letters": letters,
        "tin": tin,
        "error": error
    })