"""Original code-native editorial illustrations, selected by article subject.

Objects are conceptual illustrations, never depictions of real products,
clinical outcomes, official certificates, or numerical performance claims.
"""
from PIL import Image, ImageDraw, ImageFilter

SUBJECTS = (
    ('footcare', ('발톱', '무좀')),
    ('spreadsheet', ('엑셀', '스프레드시트', 'excel')),
    ('vacuum', ('청소기',)),
    ('air', ('공기청정기', '제습기')),
    ('laptop', ('노트북', '맥북', '컴퓨터', '윈도우')),
    ('phone', ('아이폰', '갤럭시', '스마트폰')),
    ('router', ('와이파이', '공유기', '네트워크')),
    ('wallet', ('세금', '환급', '요금', '장려금', '세액', '계산서')),
    ('calendar', ('일정', '기간', '접수', '예방접종')),
    ('health', ('건강', '검진', '치료', '증상', '혈압', '혈당')),
    ('career', ('취업', '채용', '면접', '자격증', '시험')),
    ('notebook', ('노션', '메모', '시간관리', '독서')),
    ('home', ('주거', '전입', '월세', '전세', '주택')),
)
DEFAULTS = {'건강': 'health', '취업': 'career', '생산성': 'notebook',
            '테크': 'laptop', '생활정보': 'document', '리뷰': 'document'}
PALETTES = {
    'footcare': ('#EDF5F3', '#173D38', '#438E80', '#D1E5DD'),
    'health': ('#F0F5FA', '#243D59', '#4887B2', '#D2E4F2'),
    'spreadsheet': ('#ECF4EF', '#183D32', '#398261', '#CCE3D6'),
    'vacuum': ('#F1F0F7', '#39344F', '#8271B3', '#DED8EE'),
    'air': ('#EDF4F8', '#263F52', '#5B97B7', '#D0E5ED'),
    'laptop': ('#EFF1FA', '#283357', '#6278BB', '#D4DCF4'),
    'phone': ('#F7EEF2', '#512C43', '#B66C93', '#EED1E0'),
    'router': ('#EEF3FA', '#263E5D', '#5D8DBD', '#D2E2F3'),
    'wallet': ('#F7F1E7', '#4C3C24', '#B38943', '#EDDFC2'),
    'calendar': ('#FCF0EC', '#643E33', '#C5816B', '#F1D8CE'),
    'career': ('#F0F1F8', '#353C59', '#7887B5', '#DCDFEE'),
    'notebook': ('#F4EFF8', '#473657', '#9B7BB7', '#E4D7EF'),
    'home': ('#F4F3EC', '#3C4933', '#8E9E69', '#E2E7D0'),
    'document': ('#EEF3F6', '#314351', '#6C94AB', '#D8E5ED'),
}


def subject_for(title, category=''):
    text = title.lower().replace(' ', '')
    return next((subject for subject, terms in SUBJECTS if any(t in text for t in terms)),
                DEFAULTS.get(category, 'document'))


def illustration(subject, variant=0):
    """Render at 2x then reduce for smooth curves on small WordPress cards."""
    _, ink, accent, light = PALETTES[subject]
    canvas = Image.new('RGBA', (1000, 900))
    d = ImageDraw.Draw(canvas)
    def box(xy, color, radius=24, outline=None, width=3):
        d.rounded_rectangle(tuple(int(v * 2) for v in xy), radius=radius * 2,
                            fill=color, outline=outline, width=width * 2)
    def line(points, color=ink, width=5):
        d.line([(int(x * 2), int(y * 2)) for x, y in points], fill=color, width=width * 2, joint='curve')
    def ellipse(xy, color, outline=None, width=3):
        d.ellipse(tuple(int(v * 2) for v in xy), fill=color, outline=outline, width=width * 2)
    def polygon(points, color):
        d.polygon([(int(x * 2), int(y * 2)) for x, y in points], fill=color)
    paper = '#FFFFFF'
    shadow = Image.new('RGBA', canvas.size)
    sd = ImageDraw.Draw(shadow)
    sd.ellipse((130, 734, 880, 811), fill=ink + '24')
    canvas.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(19)))
    if variant == 0:
        ellipse((40, 45, 450, 410), light)
    elif variant == 1:
        box((44, 53, 448, 402), light, 94)
    else:
        ellipse((40, 89, 371, 415), light)
        ellipse((193, 36, 453, 295), light)
    if subject in ('laptop', 'spreadsheet'):
        box((64, 102, 429, 326), ink, 18)
        box((79, 117, 414, 309), paper, 9)
        box((79, 117, 414, 148), accent, 8)
        for x in (96, 110, 124):
            ellipse((x, 128, x + 5, 133), paper)
        if subject == 'spreadsheet':
            for row in range(4):
                for col in range(4):
                    box((99 + col * 74, 166 + row * 30, 162 + col * 74, 186 + row * 30),
                        accent if (col + row + variant) % 5 == 0 else light, 3)
        else:
            box((103, 172, 240, 283), light, 10)
            ellipse((134, 191, 208, 265), accent)
            for i, width in enumerate((132, 95, 117, 78)):
                box((261, 183 + i * 27, 261 + width, 191 + i * 27), ink if i == 0 else light, 3)
        polygon([(64, 326), (429, 326), (467, 364), (27, 364)], '#BDC7D6')
        box((27, 360, 467, 377), ink, 8)
        box((202, 326, 289, 338), light, 4)
    elif subject == 'vacuum':
        # An unbranded stick vacuum and its robot counterpart show the subject.
        line([(194, 185), (140, 355)], ink, 15)
        line([(194, 185), (140, 355)], '#D0CEDB', 8)
        box((153, 72, 230, 189), accent, 27)
        box((164, 98, 219, 162), light, 16)
        line([(219, 96), (263, 112), (250, 169), (224, 154)], ink, 12)
        box((75, 344, 198, 377), ink, 12)
        box((86, 353, 187, 365), accent, 4)
        ellipse((269, 272, 447, 386), ink)
        ellipse((268, 255, 447, 365), paper)
        ellipse((315, 278, 399, 328), light)
        ellipse((340, 291, 368, 310), accent)
        line([(398, 325), (420, 322)], accent, 5)
    elif subject in ('air', 'router'):
        if subject == 'air':
            box((145, 80, 354, 369), paper, 42)
            ellipse((168, 104, 331, 175), ink)
            ellipse((185, 117, 314, 163), accent)
            for i in range(7):
                line([(173, 223 + i * 14), (325, 223 + i * 14)], light, 4)
            ellipse((243, 194, 255, 206), accent)
            for i in range(3):
                line([(81 - i * 10, 177 + i * 44), (118, 169 + i * 44)], accent, 4)
        else:
            line([(156, 289), (123, 169)], ink, 9)
            line([(350, 289), (381, 169)], ink, 9)
            box((118, 271, 383, 356), paper, 24)
            for i in range(4):
                ellipse((152 + i * 22, 315, 159 + i * 22, 322), accent)
            for radius in (41, 74, 108):
                d.arc((int((250-radius)*2), int((173-radius)*2), int((250+radius)*2), int((173+radius)*2)),
                      214, 326, fill=accent, width=12)
            ellipse((242, 150, 257, 165), ink)
    elif subject == 'phone':
        box((153, 50, 346, 397), ink, 31)
        box((164, 61, 335, 386), paper, 23)
        box((205, 70, 294, 86), ink, 10)
        ellipse((183, 118, 314, 249), light)
        ellipse((206, 141, 291, 226), accent)
        for i in range(3):
            box((185, 275 + i * 27, 313 - i * 23, 287 + i * 27), light, 5)
        box((218, 365, 282, 371), ink, 3)
    elif subject == 'footcare':
        # Stylized clean foot outline; no diseased imagery or before/after claim.
        box((129, 142, 266, 369), '#E7BCAB', 67)
        ellipse((158, 100, 251, 201), '#E7BCAB')
        for x, y, size in ((249, 139, 44), (278, 164, 38), (296, 193, 33), (302, 223, 29)):
            ellipse((x, y, x + size, y + size + 10), '#E7BCAB')
        box((183, 117, 226, 153), '#FFF9F5', 13)
        line([(172, 217), (163, 245), (164, 276)], '#BE8F7F', 3)
        box((314, 268, 391, 359), paper, 15)
        box((325, 246, 380, 278), ink, 9)
        box((322, 301, 383, 333), accent, 4)
        ellipse((77, 328, 151, 365), paper)
        line([(92, 344), (132, 347)], light, 4)
    elif subject == 'health':
        box((99, 102, 260, 364), paper, 26)
        box((119, 75, 240, 119), ink, 12)
        box((117, 183, 242, 289), light, 8)
        box((164, 203, 195, 265), accent, 5)
        box((148, 219, 211, 249), accent, 5)
        box((298, 211, 392, 359), '#E6DAD2', 39)
        box((298, 211, 392, 285), accent, 34)
        line([(309, 285), (379, 285)], paper, 3)
        ellipse((337, 116, 399, 178), paper)
    elif subject == 'wallet':
        box((83, 158, 373, 363), accent, 24)
        box((114, 110, 342, 213), paper, 10)
        for i in range(3):
            line([(142, 135 + i * 22), (313 - i * 18, 135 + i * 22)], light, 7)
        box((83, 199, 373, 364), ink, 24)
        box((298, 240, 396, 312), accent, 14)
        ellipse((319, 265, 338, 284), light)
        for x, y in ((366, 148), (400, 327)):
            ellipse((x-24, y-24, x+24, y+24), '#D7B976', '#A88849', 2)
            line([(x, y-10), (x, y+10)], '#8B6C30', 3)
    elif subject == 'calendar':
        box((83, 114, 415, 368), paper, 21)
        box((83, 114, 415, 180), accent, 21)
        for x in (151, 348):
            box((x-8, 88, x+8, 136), ink, 8)
        for row in range(3):
            for col in range(5):
                x, y = 114 + col * 58, 211 + row * 47
                box((x, y, x + 32, y + 27), accent if (row*5+col) == 6+variant else light, 6)
    elif subject == 'home':
        polygon([(103, 204), (249, 87), (401, 204)], ink)
        box((123, 196, 378, 365), paper, 5)
        box((225, 261, 285, 365), accent, 8)
        for x in (148, 303):
            box((x, 229, x + 48, 282), light, 6)
        ellipse((315, 296, 351, 332), accent)
        line([(333, 332), (333, 380), (357, 380)], accent, 10)
    else:
        # Document/study/career retain distinct objects instead of a text-only card.
        box((107, 87, 348, 361), ink, 14)
        box((122, 75, 363, 349), paper, 14)
        if subject == 'career':
            ellipse((203, 109, 278, 184), light)
            ellipse((226, 122, 254, 150), accent)
            box((214, 154, 266, 174), accent, 12)
        else:
            box((151, 111, 334, 160), light, 7)
        for i in range(4):
            x, y = 154, 210 + i * 27
            box((x, y, x + 12, y + 12), accent, 3)
            box((x + 28, y + 2, 320 - (i % 2) * 32, y + 9), light, 3)
        polygon([(366, 135), (388, 146), (298, 327), (278, 315)], accent)
        polygon([(278, 315), (298, 327), (272, 346)], ink)
        if subject == 'notebook':
            for y in range(98, 324, 35):
                line([(109, y), (135, y)], accent, 5)
    return canvas.resize((500, 450), Image.Resampling.LANCZOS)
