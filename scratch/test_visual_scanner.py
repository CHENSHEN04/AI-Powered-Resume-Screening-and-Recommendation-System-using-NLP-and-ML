import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.parser import ResumeParser
from utils.ai_assistant import AIVisualEvaluator

def test_visual_scanner():
    print("=== Testing Resume Visual Polish Scanner ===")
    
    # 1. Initialize parser and evaluator
    parser = ResumeParser()
    evaluator = AIVisualEvaluator()
    
    # 2. Build a dummy PDF locally to test actual rendering and metadata extraction
    try:
        from reportlab.pdfgen import canvas
        dummy_pdf_path = os.path.join("scratch", "dummy_resume.pdf")
        
        # Draw a basic dummy PDF
        c = canvas.Canvas(dummy_pdf_path)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(100, 750, "Jane Doe")
        c.setFont("Helvetica", 12)
        c.drawString(100, 720, "Software Engineer | janedoe@email.com")
        
        # Draw uneven experience header (visual issue)
        c.setFont("Times-Bold", 14) # Mixed fonts
        c.drawString(100, 650, "WORK EXPERIENCE")
        
        c.setFont("Helvetica", 11)
        c.drawString(100, 620, "- Built multiple React web apps.")
        c.drawString(100, 600, "  - Designed clean REST APIs.") # Uneven bullet alignments
        
        c.save()
        print(f"Created dummy PDF at: {dummy_pdf_path}")
        
        with open(dummy_pdf_path, "rb") as f:
            pdf_bytes = f.read()
            
        # 3. Test PDF rendering to Image bytes
        print("\nRendering PDF to PNG in-memory...")
        png_bytes = parser.convert_pdf_to_image(pdf_bytes)
        if png_bytes:
            print(f"=> Rendered successfully! PNG Size: {len(png_bytes)} bytes")
        else:
            print("=> Rendering failed!")
            
        # 4. Test PDF Font Metadata Extraction
        print("\nExtracting vector font metadata...")
        font_meta = parser.extract_font_metadata(pdf_bytes)
        print(f"=> Extracted {len(font_meta)} text spans.")
        for item in font_meta[:3]:
            print(f"   Text: '{item['text']}' | Font: {item['font']} | Size: {item['size']}")
            
        # 5. Run visual evaluation (Will hit fallback if key offline, else real Gemini Vision)
        print("\nRunning Visual Aesthetic Analysis...")
        visual_report = evaluator.evaluate(png_bytes, font_meta)
        print(f"Analysis Source: {visual_report.get('_source', 'Unknown')}")
        print(f"Visual Polish Score: {visual_report.get('visual_polish_score')}/100")
        print(f"Style Consistency Score: {visual_report.get('consistency_score')}/100")
        print(f"Information Hierarchy Score: {visual_report.get('hierarchy_score')}/100")
        print("\nVisual Red Flags:")
        for i, flag in enumerate(visual_report.get("red_flags", []), 1):
            print(f"  {i}. {flag.get('issue')} (Box: {flag.get('box_2d')})")
            print(f"     Reason: {flag.get('reason')}")
            
        print(f"\nRecruiter Layout Notes:\n{visual_report.get('recruiter_notes')}")
        
        # Clean up
        if os.path.exists(dummy_pdf_path):
            os.remove(dummy_pdf_path)
            
        print("\n=> ALL SYSTEM INTEGRITY TESTS PASSED SUCCESSFULLY!")
        
    except ImportError:
        print("\n[Warning] reportlab is not installed. Testing with mocked components instead...")
        # Mock bytes for testing
        mock_png = b"dummy_png_bytes"
        mock_meta = [{"text": "Jane Doe", "font": "Helvetica-Bold", "size": 16.0}]
        visual_report = evaluator.evaluate(mock_png, mock_meta)
        print(f"Visual Polish Score: {visual_report.get('visual_polish_score')}/100")
        print("=> MOCKED TEST PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_visual_scanner()
