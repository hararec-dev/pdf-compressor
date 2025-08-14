# -----------------------------------------------------------------------------
# ADAPTIVE SCRIPT TO COMPRESS PDF FILES
# -----------------------------------------------------------------------------
#
# Description:
# This script compresses PDF files to meet a specific size target. It uses an
# adaptive, multi-step compression strategy:
#
# 1. Gentle Compression: Optimizes the PDF structure without quality loss.
# 2. Adaptive Loop: If the file is still too large, it enters a loop that
#    progressively reduces the quality of embedded images until the file
#    size is below the target defined in the .env file.
#
# -----------------------------------------------------------------------------
# INSTALLATION AND USAGE
# -----------------------------------------------------------------------------
#
# 1. Install dependencies:
#    pipenv install pikepdf tqdm python-dotenv Pillow
#
# 2. Create a .env file in the root directory with the line:
#    MAX_FILE_SIZE_KB=300
#
# 3. Place your PDFs in the 'input_pdfs' folder.
#
# 4. Run the script:
#    pipenv run python main.py
#
# -----------------------------------------------------------------------------

import os
import pikepdf
from tqdm import tqdm
from dotenv import load_dotenv
from PIL import Image
import io

# Load environment variables from .env file
load_dotenv()

def apply_image_compression(input_path, output_path, quality):
    """
    Opens a PDF, recompresses its images to a specific JPEG quality,
    and saves the result to the output path.
    """
    try:
        pdf = pikepdf.open(input_path)
        
        images_processed = 0
        for obj in pdf.objects:
            if isinstance(obj, pikepdf.Stream) and '/Subtype' in obj and obj['/Subtype'] == '/Image':
                try:
                    pil_image = Image.open(io.BytesIO(obj.read_bytes()))
                    
                    # Re-compress the image as JPEG to reduce size
                    img_bytes = io.BytesIO()
                    # Convert to RGB to ensure compatibility with JPEG
                    pil_image.convert('RGB').save(img_bytes, format='JPEG', quality=quality, optimize=True)
                    
                    # Update the image stream in the PDF
                    obj.write(img_bytes.getvalue())
                    obj['/Filter'] = '/DCTDecode' # DCTDecode is the filter for JPEG
                    images_processed += 1
                except Exception:
                    # Skip images that can't be processed by Pillow
                    continue
        
        if images_processed > 0:
            pdf.save(output_path)
        pdf.close()
        return images_processed > 0
    except Exception as e:
        tqdm.write(f"  -> Error during image processing: {e}")
        return False


def main():
    """
    Main function to find, process, and adaptively compress PDF files.
    """
    input_folder = 'input_pdfs'
    output_folder = 'output_pdfs'

    # Get max file size from .env or use 300KB as default
    max_size_kb = int(os.getenv('MAX_FILE_SIZE_KB', 300))
    max_size_bytes = max_size_kb * 1024
    
    print(f"Target maximum file size set to: {max_size_kb} KB")

    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    if not os.path.exists(input_folder):
        print(f"Error! The folder '{input_folder}' does not exist.")
        return

    pdf_files = [f for f in os.listdir(input_folder) if f.lower().endswith('.pdf')]

    if not pdf_files:
        print(f"No PDF files found in '{input_folder}'.")
        return

    print(f"Found {len(pdf_files)} PDF files to process.")

    for file_name in tqdm(pdf_files, desc="Compressing PDFs"):
        input_path = os.path.join(input_folder, file_name)
        output_path = os.path.join(output_folder, file_name)

        try:
            # --- Step 1: Gentle Compression (lossless) ---
            with pikepdf.open(input_path) as pdf:
                pdf.save(output_path, compress_streams=True, linearize=True)
            
            # --- Step 2: Check size and start adaptive compression loop if needed ---
            file_size = os.path.getsize(output_path)
            
            if file_size > max_size_bytes:
                tqdm.write(f"\n'{file_name}' is too large ({file_size / 1024:.1f} KB). Starting adaptive compression...")
                
                # Start with high quality and decrease until size is met
                # The loop will read the last saved output and re-compress it
                for quality in range(80, 10, -10): # Tries 80, 70, 60, 50, 40, 30, 20
                    tqdm.write(f"  -> Attempting compression with image quality={quality}...")
                    
                    # Apply compression, reading and overwriting the output file
                    success = apply_image_compression(output_path, output_path, quality)
                    
                    if not success:
                        tqdm.write("  -> No images found to compress further.")
                        break

                    file_size = os.path.getsize(output_path)
                    tqdm.write(f"     -> New size: {file_size / 1024:.1f} KB")

                    if file_size <= max_size_bytes:
                        tqdm.write("  -> Target size achieved!")
                        break # Exit the quality loop
                
                if file_size > max_size_bytes:
                    tqdm.write(f"  -> Warning: Could not reduce '{file_name}' below target size. Final size is {file_size / 1024:.1f} KB.")

        except Exception as e:
            tqdm.write(f"\nCould not process file '{file_name}'. Error: {e}")

    print("\nProcess completed!")
    print(f"The compressed files are in: '{output_folder}'")

if __name__ == "__main__":
    main()
