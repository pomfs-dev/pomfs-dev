import os
from PIL import Image, ImageDraw, ImageFont
import requests
from io import BytesIO
from mistralai import Mistral
import textwrap

class MarketingGenerator:
    def __init__(self, api_key=None):
        self.api_key = api_key
        # Font paths - Fallback strategy
        self.font_path = "/System/Library/Fonts/Supplemental/Arial.ttf" # Mac specific
        if not os.path.exists(self.font_path):
             self.font_path = "/System/Library/Fonts/Helvetica.ttc" # Another Mac try
        if not os.path.exists(self.font_path):
             self.font_path = None # Will use default

    def _get_font(self, size):
        if self.font_path and os.path.exists(self.font_path):
            try:
                return ImageFont.truetype(self.font_path, size)
            except:
                pass
        return ImageFont.load_default()

    def generate_image(self, events, output_path="static/marketing_output.jpg"):
        """
        Generates a 1080x1080 grid image for up to 4 events.
        """
        canvas_size = (1080, 1080)
        bg_color = (26, 27, 35) # Dark theme #1a1b23
        canvas = Image.new('RGB', canvas_size, color=bg_color)
        draw = ImageDraw.Draw(canvas)
        
        # Header
        f_header = self._get_font(60) # Large for title
        # draw.text((50, 50), "🔥 THIS WEEK'S LINEUP", font=f_header, fill='#39ff14')
        # Using simple layout
        
        num_events = min(len(events), 4)
        if num_events == 0:
            return None
        
        # Grid Layout Calculation
        # 2x2 Grid
        cell_w, cell_h = 540, 540
        positions = [(0,0), (540,0), (0,540), (540,540)]
        
        for i in range(num_events):
            event = events[i]
            x, y = positions[i]
            
            # Load Image
            img_path = event.get('image_path') or event.get('imageUrl')
            poster = None
            
            if img_path:
                try:
                    # Check if local or url
                    if img_path.startswith('http'):
                        resp = requests.get(img_path)
                        poster = Image.open(BytesIO(resp.content))
                    elif os.path.exists(img_path):
                        poster = Image.open(img_path)
                    
                    if poster:
                        poster = poster.convert('RGB')
                        # Resize to fill cell (Center Crop)
                        img_ratio = poster.width / poster.height
                        target_ratio = cell_w / cell_h
                        
                        if img_ratio > target_ratio:
                            # Too wide
                            new_h = cell_h
                            new_w = int(new_h * img_ratio)
                        else:
                            # Too tall
                            new_w = cell_w
                            new_h = int(new_w / img_ratio)
                            
                        poster = poster.resize((new_w, new_h), Image.Resampling.LANCZOS)
                        
                        # Crop center
                        left = (new_w - cell_w) / 2
                        top = (new_h - cell_h) / 2
                        poster = poster.crop((left, top, left + cell_w, top + cell_h))
                        
                        # Paste
                        canvas.paste(poster, (x, y))
                        
                        # Dark Overlay for Text Readability
                        overlay = Image.new('RGBA', (cell_w, int(cell_h*0.3)), (0,0,0,180))
                        canvas.paste(overlay, (x, y + int(cell_h*0.7)), overlay)
                        
                except Exception as e:
                    print(f"Error loading image for {event['eventName']}: {e}")
            
            # Draw Text Info
            f_title = self._get_font(30)
            f_sub = self._get_font(20)
            
            # Truncate title
            title = event.get('eventName', 'Unknown')
            if len(title) > 15: title = title[:15] + "..."
            
            # Text Position
            tx, ty = x + 20, y + cell_h - 100
            if num_events == 1:
                 # Special Case: Single Poster needs different layout? 
                 # For simplicity, stick to grid but full size if 1?
                 pass 
            
            draw.text((tx, ty), title, font=f_title, fill='white')
            draw.text((tx, ty + 40), f"{event.get('venueName', '')} | {event.get('date', '')}", font=f_sub, fill='#cccccc')

        # Watermark / Branding overlay
        # Center logo or Title
        # Let's draw a centered title box
        title_box_w, title_box_h = 600, 120
        bx = (1080 - title_box_w) // 2
        by = (1080 - title_box_h) // 2
        
        # box = Image.new('RGBA', (title_box_w, title_box_h), (0,0,0,200)) # Semi-transparent
        # canvas.paste(box, (bx, by), box)
        
        # draw.text((bx + 20, by + 30), "📅 WEEKLY GIGS", font=f_header, fill='#39ff14')

        # Save
        canvas.save(output_path)
        return output_path

    def generate_caption(self, events):
        """
        Uses Mistral API to write a caption.
        """
        if not self.api_key:
            return "API Key missing. Cannot generate caption."
            
        # Format list for prompt
        event_list_text = ""
        for i, e in enumerate(events):
            event_list_text += f"{i+1}. {e['date']} [{e['venueName']}] - {e['eventName']} (Cast: {e['performers']})\n"
            
        prompt = f"""
        You are a hip editor for an Indie Music Magazine called 'P.O.M.F.S'.
        Write an Instagram caption for this week's gig lineup.
        
        Tone: Exciting, Hip, energetic. Use emojis.
        Language: Korean (Mainly), English (Keywords).
        
        Events:
        {event_list_text}
        
        Requirements:
        1. Start with a catchy hook headline.
        2. Briefly mention the key highlights.
        3. Include a call to action (Check bio for details).
        4. Add 10 relevant hashtags at the bottom.
        
        Output just the caption text.
        """
        
        try:
            client = Mistral(api_key=self.api_key)
            resp = client.chat.complete(
                model="mistral-small-latest",
                messages=[{"role": "user", "content": prompt}]
            )
            return resp.choices[0].message.content
        except Exception as e:
            return f"AI Generation Failed: {e}"
