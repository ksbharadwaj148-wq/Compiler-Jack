import re


class JackTokenizer:
    KEYWORDS = {
        "class", "constructor", "function", "method", "field", "static",
        "var", "int", "char", "boolean", "void", "true", "false", "null",
        "this", "let", "do", "if", "else", "while", "return"
    }
    SYMBOLS = set("{}()[].,;+-*/&|<>=~")

    TOKEN_RE = re.compile(
        r'"[^"\n]*"|[{}()\[\].,;+\-*/&|<>=~]|[A-Za-z_]\w*|\d+'
    )

    def __init__(self, file_path):
        self.file_path = file_path
        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()

        # Remove comments without accidentally removing comment-like text in strings.
        source = re.sub(
            r'"[^"\n]*"|//[^\n]*|/\*.*?\*/',
            lambda m: m.group(0) if m.group(0).startswith('"') else " ",
            source,
            flags=re.DOTALL
        )
        self.tokens = self.TOKEN_RE.findall(source)
        self.current_index = -1
        self.current_token = None
        self.token_type = None

    def has_more_tokens(self):
        return self.current_index + 1 < len(self.tokens)

    def advance(self):
        if not self.has_more_tokens():
            self.current_token = None
            self.token_type = None
            return
        self.current_index += 1
        self.current_token = self.tokens[self.current_index]
        self._set_token_type()

    def _set_token_type(self):
        token = self.current_token
        if token in self.KEYWORDS:
            self.token_type = "KEYWORD"
        elif token in self.SYMBOLS:
            self.token_type = "SYMBOL"
        elif token.startswith('"'):
            self.token_type = "STRING_CONST"
        elif token.isdigit():
            self.token_type = "INT_CONST"
        else:
            self.token_type = "IDENTIFIER"

    def keyword(self):
        return self.current_token

    def symbol(self):
        return self.current_token

    def identifier(self):
        return self.current_token

    def int_val(self):
        return int(self.current_token)

    def string_val(self):
        return self.current_token[1:-1]
