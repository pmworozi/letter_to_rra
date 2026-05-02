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
from PIL import Image as PILImage
import io

def home(request):
    return render(request, "core/home.html")  # or index.html if you're using that

def index(request):
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

        # =========================
        # VALIDATION
        # =========================

        if not re.fullmatch(r"1\d{8}", tin):
            return JsonResponse({"error": "TIN must start with 1 and be 9 digits"}, status=400)

        if name and not re.fullmatch(r"[A-Za-z0-9 ]{2,30}", name):
            return JsonResponse({"error": "Name must be 2–30 characters (letters/numbers only)"}, status=400)

        if not signature_file:
            return JsonResponse({"error": "Signature is required"}, status=400)

        if signature_file.content_type not in ["image/jpeg", "image/png"]:
            return JsonResponse({"error": "Signature must be JPG or PNG"}, status=400)

        # =========================
        # PROCESS SIGNATURE (SAFE + ORIGINAL QUALITY)
        # =========================

        try:
            image = PILImage.open(signature_file)

            # Ensure it's a real image
            image.verify()
            signature_file.seek(0)
            image = PILImage.open(signature_file)

        except (UnidentifiedImageError, OSError):
            return JsonResponse(
                {"error": "Invalid signature file. Please upload a valid JPG or PNG image."},
                status=400
            )

        # Normalize mode only if needed
        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGBA")

        # Only resize if image is TOO LARGE (not always)
        max_width, max_height = 1000, 500

        if image.width > max_width or image.height > max_height:
            image.thumbnail((max_width, max_height), PILImage.LANCZOS)

            buffer_img = io.BytesIO()
            image.save(buffer_img, format=image.format or "PNG")  # keep original format
            buffer_img.seek(0)

            signature_file = ContentFile(
                buffer_img.read(),
                name=f"{tin}_signature.png"
            )

        # 👉 If image is already small, keep it AS-IS (no processing)

        # =========================
        # SAVE PROFILE
        # =========================

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
        try:
            formatted_payment = "{:,.0f}".format(float(initial_payment))
        except (TypeError, ValueError):
            formatted_payment = initial_payment

        # =========================
        # NUMERIC VALIDATION
        # =========================

        # Ensure months is numeric
        try:
            months = int(months)
        except (TypeError, ValueError):
            return JsonResponse({"error": "Months must be a number"}, status=400)

        if months < 2 or months > 12:
            return JsonResponse(
                {"error": "Months must be between 2 and 12"},
                status=400
            )

        # Ensure initial payment is numeric
        try:
            initial_payment = float(initial_payment)
        except (TypeError, ValueError):
            return JsonResponse({"error": "Initial payment must be a number"}, status=400)

        if initial_payment < 50000 or initial_payment > 5000000:
            return JsonResponse(
                {"error": "Initial payment must be between 50,000 and 5,000,000"},
                status=400
            )

        # =========================
        # GENERATE LETTER
        # =========================

        letter_text = generate_letter(
            profile,
            language=language,
            months=months,
            initial_payment=initial_payment
        )

        buffer = BytesIO()

        # ✅ FIXED MARGINS
        doc = SimpleDocTemplate(
            buffer,
            leftMargin=40,
            rightMargin=40,
            topMargin=40,
            bottomMargin=40
        )

        styles = getSampleStyleSheet()

        clean = ParagraphStyle(
            name="Clean",
            parent=styles["Normal"],
            leftIndent=0,
            spaceBefore=0,
            spaceAfter=0
        )

        bold = ParagraphStyle(
            name="Bold",
            parent=clean,
            fontName="Helvetica-Bold"
        )

        right_style = ParagraphStyle(
            name="Right",
            parent=clean,
            alignment=TA_RIGHT
        )

        # Extract date safely
        lines = letter_text.splitlines()
        date_line = next((l for l in lines if "Date:" in l), "")

        # =========================
        # HEADER (FIXED ALIGNMENT)
        # =========================

        header_table = Table([
            [
                Paragraph(
                    f"{profile.name}<br/>TIN: {profile.tin}<br/>Tel: {profile.phone}<br/>Email: {profile.email}",
                    clean
                ),
                Paragraph(f"{date_line}", right_style)
            ]
        ], colWidths=[350, 150])

        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))

        content = []
        content.append(header_table)
        content.append(Spacer(1, 25))

        # =========================
        # BODY (NO INDENTATION)
        # =========================

        if language == "rw":
            content.append(Paragraph(
                f"Nanditse nsaba kwishyura mu byiciro umusoro mbereyemo RRA. Nkaba nifuza kwishyura uwo musoro mu mezi {months}.",
                clean
            ))
            content.append(Spacer(1, 10))

            content.append(Paragraph(
                f"Nkuko nabisabwe, nkaba nishyuye icyiciro cya mbere kingana na {formatted_payment}.",
                clean

            ))
           
            content.append(Spacer(1, 10))

            content.append(Paragraph(
                f"Mu gihe ngitegereje igisubizo cyanyu cyiza mbaye mbashimiye.",
                clean
            ))
            content.append(Spacer(1, 30))

        else:
            content.append(Paragraph(
                "I am writing to request permission to pay my outstanding tax liabilities in installments.",
                clean
            ))
            content.append(Spacer(1, 10))

            content.append(Paragraph(
                f"I propose to settle the amount over a period of {months} months.",
                clean
            ))
            content.append(Spacer(1, 10))

            content.append(Paragraph(
                f"As required, I have already made an initial payment of {formatted_payment}.",
                clean
            ))
            content.append(Spacer(1, 10))

            content.append(Paragraph(
                f"While awaiting your positive response, I thank you in advance.",
                clean
            ))

            content.append(Spacer(1, 10))

            content.append(Paragraph(
                f"Yours faithfully,",
                clean
            ))

            content.append(Spacer(1, 30))


        # =========================
        # SIGNATURE (LEFT PERFECT)
        # =========================

        # =========================
        # SIGNATURE (MATCH PYTHONANYWHERE SIZE)
        # =========================

        sig = Image(profile.signature.path)

        # Base width
        target_width = 120
        sig.drawWidth = target_width
        sig.drawHeight = sig.imageHeight * (target_width / sig.imageWidth)

        # ✅ LIMIT HEIGHT (this is the missing piece)
        max_height = 50

        if sig.drawHeight > max_height:
            ratio = max_height / sig.drawHeight
            sig.drawHeight = max_height
            sig.drawWidth = sig.drawWidth * ratio

        signature_table = Table([[sig]], colWidths=[500])

        signature_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('LEFTPADDING', (0, 0), (0, 0), 0),
            ('RIGHTPADDING', (0, 0), (0, 0), 0),
            ('TOPPADDING', (0, 0), (0, 0), 0),
            ('BOTTOMPADDING', (0, 0), (0, 0), 0),
        ]))

        content.append(Paragraph(profile.name))
        content.append(Spacer(1, 5))
        content.append(signature_table)

        doc.build(content)

        buffer.seek(0)
        # =========================
        # SAVE PDF
        # =========================

        file_name = f"letter_{profile.tin}.pdf"
        pdf_file = ContentFile(buffer.getvalue(), name=file_name)

        GeneratedLetter.objects.update_or_create(
            profile=profile,
            defaults={"file": pdf_file}
        )

        return HttpResponse(
            buffer,
            content_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=letter.pdf"},
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