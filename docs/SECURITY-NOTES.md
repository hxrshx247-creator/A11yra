# Security notes

Published learners receive an HTML snapshot built from a DOCX fragment. The BeautifulSoup allow-list removes active elements and attributes, checks link schemes, and accepts base64 raster image URLs only when the file signature matches an allowed MIME type. Markup supplied as Word text or alt text stays escaped and readable. The HTTP Content Security Policy allows inline CSS and JavaScript only when they match the bundled reader assets' hashes. Published readers use the teacher application's origin. A separate reader origin remains a defense-in-depth option.
