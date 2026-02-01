"""
PDF Generator Module
====================
Generates professional PDF reports of the resume analysis using ReportLab.
"""

from io import BytesIO
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.barcharts import VerticalBarChart

class PDFGenerator:
    """PDF generation utility for analysis reports."""
    
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self.width, self.height = A4
        
        # Custom Styles
        self.custom_styles = {
            'Header': ParagraphStyle(
                'Header',
                parent=self.styles['Heading1'],
                fontSize=24,
                textColor=colors.HexColor('#1E3A5F'),
                spaceAfter=20,
                alignment=1 # Center
            ),
            'SubHeader': ParagraphStyle(
                'SubHeader',
                parent=self.styles['Heading2'],
                fontSize=16,
                textColor=colors.HexColor('#2E86C1'),
                spaceAfter=10
            ),
            'Body': ParagraphStyle(
                'Body',
                parent=self.styles['Normal'],
                fontSize=10,
                spaceAfter=6,
                leading=14
            ),
            'Link': ParagraphStyle(
                'Link',
                parent=self.styles['Normal'],
                fontSize=10,
                textColor=colors.blue,
                spaceAfter=6
            )
        }

    def generate_report(self, analysis_data: dict, user_name: str = "Candidate") -> BytesIO:
        """
        Generate PDF report from analysis data.
        
        Args:
            analysis_data: Dictionary containing analysis results (role, score, gaps, etc.)
            user_name: Name of the user (or "Guest")
            
        Returns:
            BytesIO object containing the PDF data
        """
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )
        
        # Content elements
        elements = []
        
        # 1. Header
        elements.append(Paragraph("Career Roadmap Report", self.custom_styles['Header']))
        elements.append(Paragraph(f"Prepared for: <b>{user_name}</b>", self.custom_styles['Body']))
        elements.append(Paragraph(f"Date: {datetime.now().strftime('%Y-%m-%d')}", self.custom_styles['Body']))
        elements.append(Spacer(1, 0.5 * inch))
        
        # 2. Executive Summary
        elements.append(Paragraph("Executive Summary", self.custom_styles['SubHeader']))
        
        # Summary Table
        role = analysis_data.get('role', 'Unknown').replace("_", " ").title()
        score = f"{analysis_data.get('match_percentage', 0):.1f}%"
        
        summary_data = [
            ['Target Role', role],
            ['Match Score', score],
            ['Analysis ID', f"#{int(datetime.now().timestamp())}"]
        ]
        
        t = Table(summary_data, colWidths=[2*inch, 3*inch])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#F2F4F4')),
            ('TEXTCOLOR', (0,0), (-1,-1), colors.black),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 12),
            ('GRID', (0,0), (-1,-1), 1, colors.white)
        ]))
        elements.append(t)
        elements.append(Spacer(1, 0.3 * inch))
        
        # 3. Gap Analysis
        elements.append(Paragraph("Gap Analysis", self.custom_styles['SubHeader']))
        
        missing_req = analysis_data.get('missing_required', [])
        missing_rec = analysis_data.get('missing_recommended', [])
        
        if not missing_req and not missing_rec:
             elements.append(Paragraph("✅ Excellent profile! No significant skill gaps detected.", self.custom_styles['Body']))
        else:
            if missing_req:
                elements.append(Paragraph("<b>Critical Missing Skills:</b>", self.custom_styles['Body']))
                for skill in missing_req:
                    elements.append(Paragraph(f"• {skill}", self.custom_styles['Body']))
                elements.append(Spacer(1, 0.1*inch))
            
            if missing_rec:
                elements.append(Paragraph("<b>Recommended for Growth:</b>", self.custom_styles['Body']))
                for skill in missing_rec:
                    elements.append(Paragraph(f"• {skill}", self.custom_styles['Body']))
        
        elements.append(Spacer(1, 0.3 * inch))
        
        # 4. Recommendations & Resources
        elements.append(Paragraph("Personalized Learning Plan", self.custom_styles['SubHeader']))
        
        learning_paths = analysis_data.get('learning_paths', {})
        recommendations = analysis_data.get('recommendations', [])
        
        # Textual Recommendations first
        for rec in recommendations:
            # Simple markdown to bolt conversion check
            rec_text = rec.replace("**", "<b>", 1).replace("**", "</b>", 1)
            elements.append(Paragraph(f"💡 {rec_text}", self.custom_styles['Body']))
        
        elements.append(Spacer(1, 0.2*inch))
        
        if learning_paths:
            data = [['Skill', 'Resource']]
            for skill, resources in learning_paths.items():
                if resources:
                    res_links = []
                    for r in resources[:2]: # Limit to top 2 per skill for PDF to save space
                        res_links.append(f'<a href="{r["url"]}" color="blue">{r["title"]}</a>')
                    data.append([skill, "\n".join(res_links)])
            
            if len(data) > 1:
                t2 = Table(data, colWidths=[2*inch, 4*inch])
                t2.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2E86C1')),
                    ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                    ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                    ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 12),
                    ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                ]))
                
                # We need to use Paragraphs inside cells for links to work properly within ReportLab's Table
                # Refactoring table data to use Paragraph flowables
                table_data_flowables = []
                # Header
                table_data_flowables.append([
                    Paragraph("<b>Skill</b>", self.custom_styles['Body']), 
                    Paragraph("<b>Resource</b>", self.custom_styles['Body'])
                ])
                
                for skill, resources in learning_paths.items():
                    if resources:
                        # Combine links into one paragraph or list of paragraphs
                        links_text = "<br/>".join([f'• <a href="{r["url"]}" color="blue">{r["title"]}</a>' for r in resources[:2]])
                        table_data_flowables.append([
                            Paragraph(skill, self.custom_styles['Body']),
                            Paragraph(links_text, self.custom_styles['Body'])
                        ])

                t3 = Table(table_data_flowables, colWidths=[2*inch, 4*inch])
                t3.setStyle(TableStyle([
                    ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
                    ('VALIGN', (0,0), (-1,-1), 'TOP'),
                    ('PADDING', (0,0), (-1,-1), 6),
                ]))
                elements.append(t3)
        
        else:
            elements.append(Paragraph("No specific learning resources found for the missing skills.", self.custom_styles['Body']))

        # Build PDF
        doc.build(elements)
        buffer.seek(0)
        return buffer
