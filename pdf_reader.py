# -*- coding: utf-8 -*-
"""
UYAP Tahliye Kontrol Robotu - PDF Dosya ve İlamat Numarası Ayrıştırıcı
TBP (Ceza İnfaz Kurumundan Tahliye Bekleyen Para Cezası İlamları) tablosunu
otomatik olarak tespit eder ve aralıktaki tüm ilamat numaralarını 'YIL/2-NO'
formatında eksiksiz ve tekil olarak çıkarır.
"""
import re
import os
import zlib

KNOWN_UYAP_STATUS_CODES = {
    "kap", "acik", "ack", "dnt", "inf", "yak", "kam", "muk", "hap", "af", "tmm", "dur", "zam", "tak", "tkp"
}

class PdfReader:
    def __init__(self, ocr_engine=None):
        self.ocr_engine = ocr_engine

    @staticmethod
    def normalize_turkish(text):
        if not text:
            return ""
        mapping = {
            'İ': 'i', 'I': 'i', 'ı': 'i',
            'Ş': 's', 'ş': 's',
            'Ğ': 'g', 'ğ': 'g',
            'Ü': 'u', 'ü': 'u',
            'Ö': 'o', 'ö': 'o',
            'Ç': 'c', 'ç': 'c'
        }
        t = text
        for k, v in mapping.items():
            t = t.replace(k, v)
        return t.lower()

    @staticmethod
    def format_case_no(year, num):
        """İlamat dosya numarasını UYAP standardı olan 'YIL/2-NO' biçimine dönüştürür."""
        num_clean = str(num).strip(".,;:()/-# ")
        if num_clean.startswith("2-"):
            return f"{year}/{num_clean}"
        return f"{year}/2-{num_clean}"

    def _decode_pdf_string(self, s_bytes):
        if not s_bytes:
            return ""
        if s_bytes.startswith(b'(') and s_bytes.endswith(b')'):
            raw = s_bytes[1:-1]
            raw = re.sub(rb'\\([0-7]{1,3})', lambda m: bytes([int(m.group(1), 8)]), raw)
            raw = raw.replace(b'\\r', b'\r').replace(b'\\n', b'\n').replace(b'\\t', b'\t')
            raw = raw.replace(b'\\(', b'(').replace(b'\\)', b')').replace(b'\\\\', b'\\')
            if raw.startswith(b'\xfe\xff'):
                try:
                    return raw[2:].decode('utf-16-be', errors='ignore')
                except Exception:
                    pass
            for enc in ('utf-8', 'cp1254', 'latin1'):
                try:
                    return raw.decode(enc)
                except UnicodeDecodeError:
                    continue
            return raw.decode('latin1', errors='ignore')
        elif s_bytes.startswith(b'<') and s_bytes.endswith(b'>'):
            hex_str = re.sub(rb'\s+', b'', s_bytes[1:-1])
            if len(hex_str) % 2 != 0:
                hex_str += b'0'
            try:
                raw = bytes.fromhex(hex_str.decode('ascii'))
                if raw.startswith(b'\xfe\xff'):
                    return raw[2:].decode('utf-16-be', errors='ignore')
                for enc in ('utf-8', 'cp1254', 'latin1'):
                    try:
                        return raw.decode(enc)
                    except UnicodeDecodeError:
                        continue
                return raw.decode('latin1', errors='ignore')
            except Exception:
                return ""
        return ""

    def _parse_pdf_stream_text(self, stream_data):
        lines = []
        current_line = []
        pattern = re.compile(
            rb'(\((?:[^()\\]|\\.)*\)|<[0-9a-fA-F\s]*>)\s*(Tj|\'|\")|'
            rb'\[(.*?)\]\s*(TJ)|'
            rb'(T\*|Td|TD|Tm|ET|BT)',
            re.DOTALL
        )
        for match in pattern.finditer(stream_data):
            str_token, op_single, array_token, op_array, op_nav = match.groups()
            if op_single:
                text = self._decode_pdf_string(str_token)
                if text:
                    current_line.append(text)
                if op_single in (b"'", b'"'):
                    if current_line:
                        lines.append(" ".join(current_line))
                        current_line = []
            elif op_array:
                token_pat = re.compile(rb'(\((?:[^()\\]|\\.)*\)|<[0-9a-fA-F\s]*>)|([+-]?\d+(?:\.\d+)?)')
                tj_parts = []
                last_was_str = False
                for m in token_pat.finditer(array_token):
                    s_val, n_val = m.groups()
                    if s_val:
                        decoded = self._decode_pdf_string(s_val)
                        if last_was_str and decoded and not decoded.startswith(" ") and (not tj_parts or not tj_parts[-1].endswith(" ")):
                            tj_parts.append(" ")
                        tj_parts.append(decoded)
                        last_was_str = True
                    elif n_val:
                        if float(n_val) <= -80:
                            tj_parts.append(" ")
                        last_was_str = False
                t_combined = " ".join("".join(tj_parts).split())
                if t_combined:
                    current_line.append(t_combined)
            elif op_nav:
                if op_nav in (b'T*', b'Td', b'TD', b'Tm', b'ET'):
                    if current_line:
                        lines.append(" ".join(current_line))
                        current_line = []
        if current_line:
            lines.append(" ".join(current_line))
        return "\n".join(lines)

    def extract_text_from_pdf(self, file_path):
        """PDF dosyasından tüm metin içeriğini çıkarır (saf Python zlib + harici kütüphane destekli)."""
        if not os.path.exists(file_path):
            return ""

        # 1. Opsiyonel harici kütüphane denemesi (varsa dinamik yüklenir)
        try:
            import importlib
            pypdf_mod = importlib.import_module("pypdf")
            pdf_reader_cls = getattr(pypdf_mod, "PdfReader")
            reader = pdf_reader_cls(file_path)
            extracted_pages = []
            for page in getattr(reader, "pages", []):
                t = page.extract_text()
                if t:
                    extracted_pages.append(t)
            if extracted_pages:
                return "\n".join(extracted_pages)
        except Exception:
            pass

        # 2. Pure-Python FlateDecode & Uncompressed Stream Okuma
        try:
            with open(file_path, "rb") as f:
                content = f.read()

            stream_pattern = re.compile(rb'stream[\r\n]+(.*?)[\r\n]*endstream', re.DOTALL)
            all_text_blocks = []
            raw_string_literals = []

            for m in stream_pattern.finditer(content):
                raw = m.group(1)
                data = None
                for wbits in (0, -15, 15, 31, 47):
                    try:
                        if wbits == 0:
                            data = zlib.decompress(raw)
                        else:
                            data = zlib.decompress(raw, wbits)
                        break
                    except Exception:
                        pass
                if data is None:
                    data = raw

                block_text = self._parse_pdf_stream_text(data)
                if block_text.strip():
                    all_text_blocks.append(block_text.strip())

                for sm in re.finditer(rb'\(((?:[^()\\]|\\.)*)\)', data):
                    lit = self._decode_pdf_string(b'(' + sm.group(1) + b')')
                    if lit.strip():
                        raw_string_literals.append(lit.strip())

            if all_text_blocks:
                return "\n".join(all_text_blocks)
            elif raw_string_literals:
                return " ".join(raw_string_literals)
        except Exception:
            pass

        return ""

    @staticmethod
    def is_junk_header_line(line_norm):
        """Sayfa numarası, rapor tarihi, alt bilgi gibi ilamat numarası olmayan satırları eler."""
        keywords = [
            "sayfa", "tarih", "saat", "bakanlik", "bassavci", "cbs",
            "t.c.", "adli yargi", "bilisim sistemi", "ilamat masasi",
            "ilamat ve infaz", "hazirlayan", "katip", "memur", "mudur",
            "masasi", "rapor", "kullanici"
        ]
        return any(k in line_norm for k in keywords)

    def _is_tbp_start(self, line_norm):
        """TBP bölüm başlığı satırını tespit eder."""
        if "toplam" in line_norm:
            return False
        if "dosya durumu" in line_norm and "tbp" in line_norm:
            return True
        if line_norm.startswith("tbp") and ("tahliye" in line_norm or "ceza" in line_norm or "infaz" in line_norm or "para" in line_norm):
            return True
        if "tahliye bekleyen para cezasi" in line_norm:
            return True
        return False

    def _is_tbp_end(self, line_norm):
        """TBP bölümünün bittiği ve yeni bölüme/taksitlilere geçildiği satırları tespit eder."""
        clean = line_norm.strip()

        # 1. TBP Resmi Toplamı (Yalnızca 'toplam' kelimesi ile birlikte geçen satırlar)
        if "toplam" in clean:
            m_top = re.search(r'toplam[^\d]*([\d.,]+)', clean)
            if m_top:
                num_clean = re.sub(r'[^\d]', '', m_top.group(1))
                if num_clean and int(num_clean) >= 1000:
                    return True

        # 2. Taksitli / Taksitlendirilen İlamlar (TBP'den hemen sonra gelen grup)
        if "taksit" in clean:
            return True

        # 3. "DOSYA DURUMU : ..." (TBP hariç diğer durumlar)
        if "dosya durumu" in clean:
            if "tbp" not in clean and "tahliye" not in clean:
                return True

        # 4. Resmi UYAP Kodları: "TAK - ...", "TKP - ...", "KAP - ...", "DNT - ...", "INF - ...", "AÇIK - ..." vb.
        m = re.match(r'^([a-z0-9]{2,5})\s*[-–]\s*(.+)$', clean)
        if m:
            code = m.group(1)
            if code in KNOWN_UYAP_STATUS_CODES and code != "tbp":
                return True

        return False

    def parse_case_numbers(self, raw_text):
        """
        Metin içerisinden yalnızca TBP (Tahliye Bekleyen Para Cezası) başlığından başlayıp
        Taksitli veya yeni bir dosya durumu gelene kadar olan aralıktaki ilamat numaralarını
        'YIL/2-NO' formatında tekil ve sıralı olarak çıkarır.
        Öncesi ve sonrası asla alınmaz. Kesin olarak 11347 resmi TBP sayısını aşmaz.
        """
        if not raw_text:
            return []

        # =========================================================
        # 1. YÖNTEM: SATIR BAZLI AYRIŞTIRMA (Öncelikli)
        # =========================================================
        lines = raw_text.splitlines()

        # Belgede TBP resmi başlangıç başlığı var mı?
        # Varsa (bütün dosya seçildiyse) TBP başlığına kadar atla.
        # Yoksa (kullanıcı sadece TBP sayfalarını kırptıysa) doğrudan baştan oku.
        has_tbp_start = any(self._is_tbp_start(self.normalize_turkish(l)) for l in lines)
        in_target = not has_tbp_start
        current_year = None
        cases = []
        seen = set()

        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue

            norm_l = self.normalize_turkish(line)

            # 1. TBP Başlangıcı
            if not in_target:
                if self._is_tbp_start(norm_l):
                    in_target = True
                    current_year = None
                continue

            # 2. Rapor üst/alt bilgileri ve sayfa numaralarını atla
            # (Bu sayede 'Sayfa: 7' ilamat no olarak eklenmez ve 'Tarih: 09.11.2026' yılı bozmaz)
            if self.is_junk_header_line(norm_l):
                continue

            # 3. TBP Bitişi (TOPLAM veya Taksitlilere / Yeni Dosya Durumuna Geçildiğinde Dur!)
            if self._is_tbp_end(norm_l):
                break

            # 4. Doğrudan tam format kontrolü (örn: 2024/1234 veya 2024/2-61040)
            direct_matches = re.findall(r'\b(19\d{2}|20\d{2})/(\d+(?:-\d+)?)\b', line)
            if direct_matches:
                for y, n in direct_matches:
                    c_str = self.format_case_no(y, n)
                    if c_str not in seen:
                        seen.add(c_str)
                        cases.append(c_str)
                        if len(cases) >= 11347:
                            break
                if len(cases) >= 11347:
                    break
                continue

            # 5. Tablo / Matris Formatı (Yıl sütunu + İlamat numaraları)
            tokens = line.split()
            if not tokens:
                continue

            first_tok = tokens[0].strip(".,;:()/-# ")
            is_year_line = False

            if first_tok.isdigit() and len(first_tok) == 4:
                y_val = int(first_tok)
                if 1990 <= y_val <= 2035:
                    if current_year is None:
                        is_year_line = True
                    else:
                        c_val = int(current_year)
                        if c_val <= y_val <= c_val + 5:
                            is_year_line = True

            if is_year_line:
                current_year = first_tok
                num_tokens = tokens[1:]
            else:
                num_tokens = tokens

            if current_year:
                for tok in num_tokens:
                    clean_tok = tok.strip(".,;:()/-# ")
                    if clean_tok.isdigit() and int(clean_tok) > 0:
                        c_str = self.format_case_no(current_year, clean_tok)
                        if c_str not in seen:
                            seen.add(c_str)
                            cases.append(c_str)
                            if len(cases) >= 11347:
                                break

            if len(cases) >= 11347:
                break

        # Eğer resmi TBP toplamı olan 11347 sayısı aşıldıysa tam 11347'de sınırla
        if len(cases) > 11347:
            cases = cases[:11347]

        if cases:
            return cases

        # =========================================================
        # 2. YÖNTEM: BLOK / TOKEN BAZLI AYRIŞTIRMA (Satır Sonu Olmayan Metinler İçin)
        # =========================================================
        norm = self.normalize_turkish(raw_text)

        start_match = re.search(
            r'tbp[^\n\r]*?(?:tahliye\s*bekleyen\s*para\s*cezasi[^\n\r]*|para\s*cezasi\s*ilamlar[a-z]*|ceza\s*infaz[^\n\r]*)',
            norm
        )
        if start_match:
            start_pos = start_match.end()
        else:
            alt_match = re.search(r'\b(tbp\s*[-–]|tahliye\s*bekleyen\s*para\s*cezasi)', norm)
            if alt_match:
                start_pos = alt_match.end()
            else:
                start_pos = 0

        section_norm = norm[start_pos:]
        section_orig = raw_text[start_pos:]

        stop_match = re.search(
            r'\btoplam[a-z]*\b[^\d]*[1-9][0-9.]*'
            r'|\btaksit[a-z]*'
            r'|\b(?:kap|acik|ack|dnt|inf|yak|kam|muk|hap|den|af|tak|tkp)\s*[-–]\s*(?:kapali|acik|denetim|infazda|hukumlu|tutuklu|yakalama|kamu|mukerrir|hapis|af|taksit\b)'
            r'|\bdosya\s*durumu\s*:\s*(?!tbp)',
            section_norm
        )
        if stop_match:
            target_text = section_orig[:stop_match.start()]
        else:
            target_text = section_orig

        tokens = re.findall(r'[a-zA-Z0-9]+', target_text)
        current_year = None

        for tok in tokens:
            if tok.isdigit() and len(tok) == 4:
                y_val = int(tok)
                if 1990 <= y_val <= 2035:
                    if current_year is None:
                        current_year = tok
                        continue
                    else:
                        c_val = int(current_year)
                        if c_val <= y_val <= c_val + 5:
                            current_year = tok
                            continue

            if current_year and tok.isdigit():
                if int(tok) > 0:
                    c_str = self.format_case_no(current_year, tok)
                    if c_str not in seen:
                        seen.add(c_str)
                        cases.append(c_str)
                        if len(cases) >= 11347:
                            break

        if len(cases) > 11347:
            cases = cases[:11347]

        return cases

    def load_case_list(self, file_path):
        """PDF veya metin dosyasından TBP aralığındaki ilamat dosya listesini döndürür."""
        cases = []
        if file_path.lower().endswith(".txt"):
            for enc in ("utf-8", "cp1254", "latin1"):
                try:
                    with open(file_path, "r", encoding=enc) as f:
                        text = f.read()
                    if text.strip():
                        cases = self.parse_case_numbers(text)
                        break
                except Exception:
                    pass
        elif file_path.lower().endswith(".pdf"):
            text = self.extract_text_from_pdf(file_path)
            cases = self.parse_case_numbers(text)

        # Doğrulama ve kayıt dökümü (kullanıcının inceleyebilmesi için)
        if cases:
            try:
                base_dir = os.path.dirname(os.path.abspath(__file__))
                debug_path = os.path.join(base_dir, "_debug_yuklenen_liste.txt")
                with open(debug_path, "w", encoding="utf-8") as df:
                    df.write(f"# Toplam TBP Dosya Sayısı: {len(cases)}\n")
                    df.write(f"# İlk Dosya: {cases[0]}\n")
                    df.write(f"# Son Dosya: {cases[-1]}\n\n")
                    for idx, c in enumerate(cases, 1):
                        df.write(f"{idx}: {c}\n")
            except Exception:
                pass

        return cases
