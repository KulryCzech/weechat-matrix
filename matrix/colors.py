# -*- coding: utf-8 -*-

# Copyright © 2008 Nicholas Marriott <nicholas.marriott@gmail.com>
# Copyright © 2016 Avi Halachmi <avihpit@yahoo.com>
# Copyright © 2018 Damir Jelić <poljar@termina.org.uk>
#
# Permission to use, copy, modify, and/or distribute this software for
# any purpose with or without fee is hereby granted, provided that the
# above copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
# SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER
# RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF
# CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN
# CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

from __future__ import unicode_literals

# pylint: disable=redefined-builtin
from builtins import str
from collections import namedtuple
from matrix.globals import W, OPTIONS
from matrix.utils import string_strikethrough

import re
import textwrap
import webcolors

from pygments import highlight
from pygments.lexers import guess_lexer, get_lexer_by_name
from pygments.formatter import Formatter
from pygments.util import ClassNotFound

try:
    from HTMLParser import HTMLParser
except ImportError:
    from html.parser import HTMLParser

import html

FormattedString = namedtuple('FormattedString', ['text', 'attributes'])


class Formatted():

    def __init__(self, substrings):
        # type: (List[FormattedString]) -> None
        self.substrings = substrings

    @property
    def textwrapper(self):
        return textwrap.TextWrapper(
            width=67,
            initial_indent="{}> ".format(
                W.color(W.config_string(OPTIONS.options["quote"]))
            ),
            subsequent_indent="{}> ".format(
                W.color(W.config_string(OPTIONS.options["quote"]))
            ))

    def is_formatted(self):
        # type: (Formatted) -> bool
        for string in self.substrings:
            if string.attributes != DEFAULT_ATRIBUTES:
                return True
        return False

    # TODO reverse video
    @classmethod
    def from_input_line(cls, line):
        # type: (str) -> Formatted
        """Parses the weechat input line and produces formatted strings that
        can be later converted to HTML or to a string for weechat's print
        functions
        """
        text = ""  # type: str
        substrings = []  # type: List[FormattedString]
        attributes = DEFAULT_ATRIBUTES.copy()

        i = 0
        while i < len(line):
            # Bold
            if line[i] == "\x02":
                if text:
                    substrings.append(FormattedString(text, attributes.copy()))
                text = ""
                attributes["bold"] = not attributes["bold"]
                i = i + 1

            # Markdown bold
            elif line[i] == "*":
                if attributes["italic"] and not line[i-1].isspace():
                    if text:
                        substrings.append(FormattedString(
                            text, attributes.copy()))
                    text = ""
                    attributes["italic"] = not attributes["italic"]
                    i = i + 1
                    continue

                elif attributes["italic"] and line[i-1].isspace():
                    text = text + line[i]
                    i = i + 1
                    continue

                elif i+1 < len(line) and line[i+1].isspace():
                    text = text + line[i]
                    i = i + 1
                    continue

                elif i == len(line) - 1:
                    text = text + line[i]
                    i = i + 1
                    continue

                if text:
                    substrings.append(FormattedString(text, attributes.copy()))
                text = ""
                attributes["italic"] = not attributes["italic"]
                i = i + 1

            # Color
            elif line[i] == "\x03":
                if text:
                    substrings.append(FormattedString(text, attributes.copy()))
                text = ""
                i = i + 1

                # check if it's a valid color, add it to the attributes
                if line[i].isdigit():
                    color_string = line[i]
                    i = i + 1

                    if line[i].isdigit():
                        if color_string == "0":
                            color_string = line[i]
                        else:
                            color_string = color_string + line[i]
                        i = i + 1

                    attributes["fgcolor"] = color_line_to_weechat(color_string)
                else:
                    attributes["fgcolor"] = None

                # check if we have a background color
                if line[i] == "," and line[i + 1].isdigit():
                    color_string = line[i + 1]
                    i = i + 2

                    if line[i].isdigit():
                        if color_string == "0":
                            color_string = line[i]
                        else:
                            color_string = color_string + line[i]
                        i = i + 1

                    attributes["bgcolor"] = color_line_to_weechat(color_string)
                else:
                    attributes["bgcolor"] = None
            # Reset
            elif line[i] == "\x0F":
                if text:
                    substrings.append(FormattedString(text, attributes.copy()))
                text = ""
                # Reset all the attributes
                attributes = DEFAULT_ATRIBUTES.copy()
                i = i + 1
            # Italic
            elif line[i] == "\x1D":
                if text:
                    substrings.append(FormattedString(text, attributes.copy()))
                text = ""
                attributes["italic"] = not attributes["italic"]
                i = i + 1

            # Underline
            elif line[i] == "\x1F":
                if text:
                    substrings.append(FormattedString(text, attributes.copy()))
                text = ""
                attributes["underline"] = not attributes["underline"]
                i = i + 1

            # Normal text
            else:
                text = text + line[i]
                i = i + 1

        substrings.append(FormattedString(text, attributes))
        return cls(substrings)

    @classmethod
    def from_html(cls, html):
        # type: (str) -> Formatted
        parser = MatrixHtmlParser()
        parser.feed(html)
        return cls(parser.get_substrings())

    def to_html(self):
        # TODO BG COLOR
        def add_attribute(string, name, value):
            if name == "bold" and value:
                return "{bold_on}{text}{bold_off}".format(
                    bold_on="<strong>", text=string, bold_off="</strong>")
            elif name == "italic" and value:
                return "{italic_on}{text}{italic_off}".format(
                    italic_on="<em>", text=string, italic_off="</em>")
            elif name == "underline" and value:
                return "{underline_on}{text}{underline_off}".format(
                    underline_on="<u>", text=string, underline_off="</u>")
            elif name == "strikethrough" and value:
                return "{strike_on}{text}{strike_off}".format(
                    strike_on="<del>", text=string, strike_off="</del>")
            elif name == "quote" and value:
                return "{quote_on}{text}{quote_off}".format(
                    quote_on="<blockquote>",
                    text=string,
                    quote_off="</blockquote>")
            elif name == "fgcolor" and value:
                return "{color_on}{text}{color_off}".format(
                    color_on="<font color={color}>".format(
                        color=color_weechat_to_html(value)),
                    text=string,
                    color_off="</font>")

            return string

        def format_string(formatted_string):
            text = formatted_string.text
            attributes = formatted_string.attributes

            for key, value in attributes.items():
                text = add_attribute(text, key, value)
            return text

        html_string = map(format_string, self.substrings)
        return "".join(html_string)

    # TODO do we want at least some formatting using unicode
    # (strikethrough, quotes)?
    def to_plain(self):
        # type: (List[FormattedString]) -> str
        def strip_atribute(string, _, __):
            return string

        def format_string(formatted_string):
            text = formatted_string.text
            attributes = formatted_string.attributes

            for key, value in attributes.items():
                text = strip_atribute(text, key, value)
            return text

        plain_string = map(format_string, self.substrings)
        return "".join(plain_string)

    def to_weechat(self):
        # TODO BG COLOR
        def add_attribute(string, name, value):
            if name == "bold" and value:
                return "{bold_on}{text}{bold_off}".format(
                    bold_on=W.color("bold"),
                    text=string,
                    bold_off=W.color("-bold"))

            elif name == "italic" and value:
                return "{italic_on}{text}{italic_off}".format(
                    italic_on=W.color("italic"),
                    text=string,
                    italic_off=W.color("-italic"))

            elif name == "underline" and value:
                return "{underline_on}{text}{underline_off}".format(
                    underline_on=W.color("underline"),
                    text=string,
                    underline_off=W.color("-underline"))

            elif name == "strikethrough" and value:
                return string_strikethrough(string)

            elif name == "quote" and value:
                return self.textwrapper.fill(
                    W.string_remove_color(string.replace("\n", ""), ""))

            elif name == "code" and value:
                try:
                    lexer = get_lexer_by_name(value)
                except ClassNotFound:
                    lexer = guess_lexer(string)

                # highlight adds a newline to the end of the string, remove it
                # from the output
                return highlight(string, lexer, WeechatFormatter())[:-1]

            elif name == "fgcolor" and value:
                return "{color_on}{text}{color_off}".format(
                    color_on=W.color(value),
                    text=string,
                    color_off=W.color("resetcolor"))

            elif name == "bgcolor" and value:
                return "{color_on}{text}{color_off}".format(
                    color_on=W.color("," + value),
                    text=string,
                    color_off=W.color("resetcolor"))

            return string

        def format_string(formatted_string):
            text = formatted_string.text
            attributes = formatted_string.attributes

            # We need to handle strikethrough first, since doing
            # a strikethrough followed by other attributes succeeds in the
            # terminal, but doing it the other way around results in garbage.
            if 'strikethrough' in attributes:
                text = add_attribute(text, 'strikethrough',
                                     attributes['strikethrough'])
                attributes.pop('strikethrough')

            for key, value in attributes.items():
                text = add_attribute(text, key, value)
            return text

        weechat_strings = map(format_string, self.substrings)
        return re.sub(r'\n+', '\n', "".join(weechat_strings)).strip()


# TODO this should be a typed dict.
DEFAULT_ATRIBUTES = {
    "bold": False,
    "italic": False,
    "underline": False,
    "strikethrough": False,
    "quote": False,
    "code": None,
    "fgcolor": None,
    "bgcolor": None
}


class MatrixHtmlParser(HTMLParser):
    # TODO bg color
    # TODO bullets
    def __init__(self):
        HTMLParser.__init__(self)
        self.text = ""  # type: str
        self.substrings = []  # type: List[FormattedString]
        self.attributes = DEFAULT_ATRIBUTES.copy()

    def unescape(self, text):
        """Shim to unescape HTML in both Python 2 and 3.

        The instance method was deprecated in Python 3 and html.unescape
        doesn't exist in Python 2 so this is needed.
        """
        try:
            return html.unescape(text)
        except AttributeError:
            return HTMLParser.unescape(self, text)

    def add_substring(self, text, attrs):
        fmt_string = FormattedString(text, attrs)
        self.substrings.append(fmt_string)

    def _toggle_attribute(self, attribute):
        if self.text:
            self.add_substring(self.text, self.attributes.copy())
        self.text = ""
        self.attributes[attribute] = not self.attributes[attribute]

    def handle_starttag(self, tag, attrs):
        if tag == "strong":
            self._toggle_attribute("bold")
        elif tag == "em":
            self._toggle_attribute("italic")
        elif tag == "u":
            self._toggle_attribute("underline")
        elif tag == "del":
            self._toggle_attribute("strikethrough")
        elif tag == "blockquote":
            self._toggle_attribute("quote")
        elif tag == "code":
            lang = None

            for key, value in attrs:
                if key == "class":
                    if value.startswith("language-"):
                        lang = value.split("-", 1)[1]

            lang = lang or "unknown"

            if self.text:
                self.add_substring(self.text, self.attributes.copy())
            self.text = ""
            self.attributes["code"] = lang
        elif tag == "p":
            if self.text:
                self.add_substring(self.text, self.attributes.copy())
            self.text = "\n"
            self.add_substring(self.text, DEFAULT_ATRIBUTES.copy())
            self.text = ""
        elif tag == "br":
            if self.text:
                self.add_substring(self.text, self.attributes.copy())
            self.text = "\n"
            self.add_substring(self.text, DEFAULT_ATRIBUTES.copy())
            self.text = ""
        elif tag == "font":
            for key, value in attrs:
                if key == "color":
                    color = color_html_to_weechat(value)

                    if not color:
                        continue

                    if self.text:
                        self.add_substring(self.text, self.attributes.copy())
                    self.text = ""
                    self.attributes["fgcolor"] = color
        else:
            pass

    def handle_endtag(self, tag):
        if tag == "strong":
            self._toggle_attribute("bold")
        elif tag == "em":
            self._toggle_attribute("italic")
        elif tag == "u":
            self._toggle_attribute("underline")
        elif tag == "del":
            self._toggle_attribute("strikethrough")
        elif tag == "code":
            if self.text:
                self.add_substring(self.text, self.attributes.copy())
            self.text = ""
            self.attributes["code"] = None
        elif tag == "blockquote":
            self._toggle_attribute("quote")
            self.text = "\n"
            self.add_substring(self.text, DEFAULT_ATRIBUTES.copy())
            self.text = ""
        elif tag == "font":
            if self.text:
                self.add_substring(self.text, self.attributes.copy())
            self.text = ""
            self.attributes["fgcolor"] = None
        else:
            pass

    def handle_data(self, data):
        self.text += data

    def handle_entityref(self, name):
        self.text += self.unescape("&{};".format(name))

    def handle_charref(self, name):
        self.text += self.unescape("&#{};".format(name))

    def get_substrings(self):
        if self.text:
            self.add_substring(self.text, self.attributes.copy())

        return self.substrings


def color_line_to_weechat(color_string):
    # type: (str) -> str
    line_colors = {
        "0": "white",
        "1": "black",
        "2": "blue",
        "3": "green",
        "4": "lightred",
        "5": "red",
        "6": "magenta",
        "7": "brown",
        "8": "yellow",
        "9": "lightgreen",
        "10": "cyan",
        "11": "lightcyan",
        "12": "lightblue",
        "13": "lightmagenta",
        "14": "darkgray",
        "15": "gray",
        "16": "52",
        "17": "94",
        "18": "100",
        "19": "58",
        "20": "22",
        "21": "29",
        "22": "23",
        "23": "24",
        "24": "17",
        "25": "54",
        "26": "53",
        "27": "89",
        "28": "88",
        "29": "130",
        "30": "142",
        "31": "64",
        "32": "28",
        "33": "35",
        "34": "30",
        "35": "25",
        "36": "18",
        "37": "91",
        "38": "90",
        "39": "125",
        "40": "124",
        "41": "166",
        "42": "184",
        "43": "106",
        "44": "34",
        "45": "49",
        "46": "37",
        "47": "33",
        "48": "19",
        "49": "129",
        "50": "127",
        "51": "161",
        "52": "196",
        "53": "208",
        "54": "226",
        "55": "154",
        "56": "46",
        "57": "86",
        "58": "51",
        "59": "75",
        "60": "21",
        "61": "171",
        "62": "201",
        "63": "198",
        "64": "203",
        "65": "215",
        "66": "227",
        "67": "191",
        "68": "83",
        "69": "122",
        "70": "87",
        "71": "111",
        "72": "63",
        "73": "177",
        "74": "207",
        "75": "205",
        "76": "217",
        "77": "223",
        "78": "229",
        "79": "193",
        "80": "157",
        "81": "158",
        "82": "159",
        "83": "153",
        "84": "147",
        "85": "183",
        "86": "219",
        "87": "212",
        "88": "16",
        "89": "233",
        "90": "235",
        "91": "237",
        "92": "239",
        "93": "241",
        "94": "244",
        "95": "247",
        "96": "250",
        "97": "254",
        "98": "231",
        "99": "default"
    }

    assert color_string in line_colors

    return line_colors[color_string]


# The functions colour_dist_sq(), colour_to_6cube(), and colour_find_rgb
# are python ports of the same named functions from the tmux
# source, they are under the copyright of Nicholas Marriott, and Avi Halachmi
# under the ISC license.
# More info: https://github.com/tmux/tmux/blob/master/colour.c


def colour_dist_sq(R, G, B, r, g, b):
    # pylint: disable=invalid-name,too-many-arguments
    # type: (int, int, int, int, int, int) -> int
    return (R - r) * (R - r) + (G - g) * (G - g) + (B - b) * (B - b)


def colour_to_6cube(v):
    # pylint: disable=invalid-name
    # type: (int) -> int
    if v < 48:
        return 0
    if v < 114:
        return 1
    return (v - 35) // 40


def colour_find_rgb(r, g, b):
    # type: (int, int, int) -> int
    """Convert an RGB triplet to the xterm(1) 256 colour palette.

       xterm provides a 6x6x6 colour cube (16 - 231) and 24 greys (232 - 255).
       We map our RGB colour to the closest in the cube, also work out the
       closest grey, and use the nearest of the two.

       Note that the xterm has much lower resolution for darker colours (they
       are not evenly spread out), so our 6 levels are not evenly spread: 0x0,
       0x5f (95), 0x87 (135), 0xaf (175), 0xd7 (215) and 0xff (255). Greys are
       more evenly spread (8, 18, 28 ... 238).
    """
    # pylint: disable=invalid-name
    q2c = [0x00, 0x5f, 0x87, 0xaf, 0xd7, 0xff]

    # Map RGB to 6x6x6 cube.
    qr = colour_to_6cube(r)
    qg = colour_to_6cube(g)
    qb = colour_to_6cube(b)

    cr = q2c[qr]
    cg = q2c[qg]
    cb = q2c[qb]

    # If we have hit the colour exactly, return early.
    if (cr == r and cg == g and cb == b):
        return 16 + (36 * qr) + (6 * qg) + qb

    # Work out the closest grey (average of RGB).
    grey_avg = (r + g + b) // 3

    if grey_avg > 238:
        grey_idx = 23
    else:
        grey_idx = (grey_avg - 3) // 10

    grey = 8 + (10 * grey_idx)

    # Is grey or 6x6x6 colour closest?
    d = colour_dist_sq(cr, cg, cb, r, g, b)

    if colour_dist_sq(grey, grey, grey, r, g, b) < d:
        idx = 232 + grey_idx
    else:
        idx = 16 + (36 * qr) + (6 * qg) + qb

    return idx


def color_html_to_weechat(color):
    # type: (str) -> str
    # yapf: disable
    weechat_basic_colors = {
        (0, 0, 0): "black",             # 0
        (128, 0, 0): "red",             # 1
        (0, 128, 0): "green",           # 2
        (128, 128, 0): "brown",         # 3
        (0, 0, 128): "blue",            # 4
        (128, 0, 128): "magenta",       # 5
        (0, 128, 128): "cyan",          # 6
        (192, 192, 192): "default",     # 7
        (128, 128, 128): "gray",        # 8
        (255, 0, 0): "lightred",        # 9
        (0, 255, 0): "lightgreen",      # 10
        (255, 255, 0): "yellow",        # 11
        (0, 0, 255): "lightblue",       # 12
        (255, 0, 255): "lightmagenta",  # 13
        (0, 255, 255): "lightcyan",     # 14
        (255, 255, 255): "white",       # 15
    }
    # yapf: enable

    try:
        rgb_color = webcolors.html5_parse_legacy_color(color)
    except ValueError:
        return None

    if rgb_color in weechat_basic_colors:
        return weechat_basic_colors[rgb_color]

    return str(colour_find_rgb(*rgb_color))


def color_weechat_to_html(color):
    # type: (str) -> str
    # yapf: disable
    weechat_basic_colors = {
        "black": "0",
        "red": "1",
        "green": "2",
        "brown": "3",
        "blue": "4",
        "magenta": "5",
        "cyan": "6",
        "default": "7",
        "gray": "8",
        "lightred": "9",
        "lightgreen": "10",
        "yellow": "11",
        "lightblue": "12",
        "lightmagenta": "13",
        "lightcyan": "14",
        "white": "15",
    }
    hex_colors = {
        "0":   "#000000",
        "1":   "#800000",
        "2":   "#008000",
        "3":   "#808000",
        "4":   "#000080",
        "5":   "#800080",
        "6":   "#008080",
        "7":   "#c0c0c0",
        "8":   "#808080",
        "9":   "#ff0000",
        "10":  "#00ff00",
        "11":  "#ffff00",
        "12":  "#0000ff",
        "13":  "#ff00ff",
        "14":  "#00ffff",
        "15":  "#ffffff",
        "16":  "#000000",
        "17":  "#00005f",
        "18":  "#000087",
        "19":  "#0000af",
        "20":  "#0000d7",
        "21":  "#0000ff",
        "22":  "#005f00",
        "23":  "#005f5f",
        "24":  "#005f87",
        "25":  "#005faf",
        "26":  "#005fd7",
        "27":  "#005fff",
        "28":  "#008700",
        "29":  "#00875f",
        "30":  "#008787",
        "31":  "#0087af",
        "32":  "#0087d7",
        "33":  "#0087ff",
        "34":  "#00af00",
        "35":  "#00af5f",
        "36":  "#00af87",
        "37":  "#00afaf",
        "38":  "#00afd7",
        "39":  "#00afff",
        "40":  "#00d700",
        "41":  "#00d75f",
        "42":  "#00d787",
        "43":  "#00d7af",
        "44":  "#00d7d7",
        "45":  "#00d7ff",
        "46":  "#00ff00",
        "47":  "#00ff5f",
        "48":  "#00ff87",
        "49":  "#00ffaf",
        "50":  "#00ffd7",
        "51":  "#00ffff",
        "52":  "#5f0000",
        "53":  "#5f005f",
        "54":  "#5f0087",
        "55":  "#5f00af",
        "56":  "#5f00d7",
        "57":  "#5f00ff",
        "58":  "#5f5f00",
        "59":  "#5f5f5f",
        "60":  "#5f5f87",
        "61":  "#5f5faf",
        "62":  "#5f5fd7",
        "63":  "#5f5fff",
        "64":  "#5f8700",
        "65":  "#5f875f",
        "66":  "#5f8787",
        "67":  "#5f87af",
        "68":  "#5f87d7",
        "69":  "#5f87ff",
        "70":  "#5faf00",
        "71":  "#5faf5f",
        "72":  "#5faf87",
        "73":  "#5fafaf",
        "74":  "#5fafd7",
        "75":  "#5fafff",
        "76":  "#5fd700",
        "77":  "#5fd75f",
        "78":  "#5fd787",
        "79":  "#5fd7af",
        "80":  "#5fd7d7",
        "81":  "#5fd7ff",
        "82":  "#5fff00",
        "83":  "#5fff5f",
        "84":  "#5fff87",
        "85":  "#5fffaf",
        "86":  "#5fffd7",
        "87":  "#5fffff",
        "88":  "#870000",
        "89":  "#87005f",
        "90":  "#870087",
        "91":  "#8700af",
        "92":  "#8700d7",
        "93":  "#8700ff",
        "94":  "#875f00",
        "95":  "#875f5f",
        "96":  "#875f87",
        "97":  "#875faf",
        "98":  "#875fd7",
        "99":  "#875fff",
        "100": "#878700",
        "101": "#87875f",
        "102": "#878787",
        "103": "#8787af",
        "104": "#8787d7",
        "105": "#8787ff",
        "106": "#87af00",
        "107": "#87af5f",
        "108": "#87af87",
        "109": "#87afaf",
        "110": "#87afd7",
        "111": "#87afff",
        "112": "#87d700",
        "113": "#87d75f",
        "114": "#87d787",
        "115": "#87d7af",
        "116": "#87d7d7",
        "117": "#87d7ff",
        "118": "#87ff00",
        "119": "#87ff5f",
        "120": "#87ff87",
        "121": "#87ffaf",
        "122": "#87ffd7",
        "123": "#87ffff",
        "124": "#af0000",
        "125": "#af005f",
        "126": "#af0087",
        "127": "#af00af",
        "128": "#af00d7",
        "129": "#af00ff",
        "130": "#af5f00",
        "131": "#af5f5f",
        "132": "#af5f87",
        "133": "#af5faf",
        "134": "#af5fd7",
        "135": "#af5fff",
        "136": "#af8700",
        "137": "#af875f",
        "138": "#af8787",
        "139": "#af87af",
        "140": "#af87d7",
        "141": "#af87ff",
        "142": "#afaf00",
        "143": "#afaf5f",
        "144": "#afaf87",
        "145": "#afafaf",
        "146": "#afafd7",
        "147": "#afafff",
        "148": "#afd700",
        "149": "#afd75f",
        "150": "#afd787",
        "151": "#afd7af",
        "152": "#afd7d7",
        "153": "#afd7ff",
        "154": "#afff00",
        "155": "#afff5f",
        "156": "#afff87",
        "157": "#afffaf",
        "158": "#afffd7",
        "159": "#afffff",
        "160": "#d70000",
        "161": "#d7005f",
        "162": "#d70087",
        "163": "#d700af",
        "164": "#d700d7",
        "165": "#d700ff",
        "166": "#d75f00",
        "167": "#d75f5f",
        "168": "#d75f87",
        "169": "#d75faf",
        "170": "#d75fd7",
        "171": "#d75fff",
        "172": "#d78700",
        "173": "#d7875f",
        "174": "#d78787",
        "175": "#d787af",
        "176": "#d787d7",
        "177": "#d787ff",
        "178": "#d7af00",
        "179": "#d7af5f",
        "180": "#d7af87",
        "181": "#d7afaf",
        "182": "#d7afd7",
        "183": "#d7afff",
        "184": "#d7d700",
        "185": "#d7d75f",
        "186": "#d7d787",
        "187": "#d7d7af",
        "188": "#d7d7d7",
        "189": "#d7d7ff",
        "190": "#d7ff00",
        "191": "#d7ff5f",
        "192": "#d7ff87",
        "193": "#d7ffaf",
        "194": "#d7ffd7",
        "195": "#d7ffff",
        "196": "#ff0000",
        "197": "#ff005f",
        "198": "#ff0087",
        "199": "#ff00af",
        "200": "#ff00d7",
        "201": "#ff00ff",
        "202": "#ff5f00",
        "203": "#ff5f5f",
        "204": "#ff5f87",
        "205": "#ff5faf",
        "206": "#ff5fd7",
        "207": "#ff5fff",
        "208": "#ff8700",
        "209": "#ff875f",
        "210": "#ff8787",
        "211": "#ff87af",
        "212": "#ff87d7",
        "213": "#ff87ff",
        "214": "#ffaf00",
        "215": "#ffaf5f",
        "216": "#ffaf87",
        "217": "#ffafaf",
        "218": "#ffafd7",
        "219": "#ffafff",
        "220": "#ffd700",
        "221": "#ffd75f",
        "222": "#ffd787",
        "223": "#ffd7af",
        "224": "#ffd7d7",
        "225": "#ffd7ff",
        "226": "#ffff00",
        "227": "#ffff5f",
        "228": "#ffff87",
        "229": "#ffffaf",
        "230": "#ffffd7",
        "231": "#ffffff",
        "232": "#080808",
        "233": "#121212",
        "234": "#1c1c1c",
        "235": "#262626",
        "236": "#303030",
        "237": "#3a3a3a",
        "238": "#444444",
        "239": "#4e4e4e",
        "240": "#585858",
        "241": "#626262",
        "242": "#6c6c6c",
        "243": "#767676",
        "244": "#808080",
        "245": "#8a8a8a",
        "246": "#949494",
        "247": "#9e9e9e",
        "248": "#a8a8a8",
        "249": "#b2b2b2",
        "250": "#bcbcbc",
        "251": "#c6c6c6",
        "252": "#d0d0d0",
        "253": "#dadada",
        "254": "#e4e4e4",
        "255": "#eeeeee"
    }

    # yapf: enable
    if color in weechat_basic_colors:
        return hex_colors[weechat_basic_colors[color]]
    else:
        return hex_colors[color]


class WeechatFormatter(Formatter):
    def __init__(self, **options):
        Formatter.__init__(self, **options)
        self.styles = {}

        for token, style in self.style:
            start = end = ""
            if style["color"]:
                start += "{}".format(
                    W.color(color_html_to_weechat(str(style["color"]))))
                end = "{}".format(W.color("resetcolor")) + end
            if style["bold"]:
                start += W.color("bold")
                end = W.color("-bold") + end
            if style["italic"]:
                start += W.color("italic")
                end = W.color("-italic") + end
            if style['underline']:
                start += W.color("underline")
                end = W.color("-underline") + end
            self.styles[token] = (start, end)

    def format(self, tokensource, outfile):
        lastval = ''
        lasttype = None

        for ttype, value in tokensource:
            while ttype not in self.styles:
                ttype = ttype.parent

            if ttype == lasttype:
                lastval += value
            else:
                if lastval:
                    stylebegin, styleend = self.styles[lasttype]
                    outfile.write(stylebegin + lastval + styleend)
                # set lastval/lasttype to current values
                lastval = value
                lasttype = ttype

        if lastval:
            stylebegin, styleend = self.styles[lasttype]
            outfile.write(stylebegin + lastval + styleend)
