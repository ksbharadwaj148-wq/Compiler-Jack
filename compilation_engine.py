class CompilationEngine:
    BINARY_OPS = {
        "+": "add", "-": "sub", "&": "and", "|": "or",
        "<": "lt", ">": "gt", "=": "eq"
    }
    UNARY_OPS = {"-": "neg", "~": "not"}

    def __init__(self, tokenizer, symbol_table, vm_writer):
        self.tokenizer = tokenizer
        self.sym_table = symbol_table
        self.vm = vm_writer
        self.class_name = ""
        self.label_counter = 0

    def _advance(self):
        self.tokenizer.advance()

    def _eat(self, expected):
        if self.tokenizer.current_token != expected:
            raise SyntaxError(
                f"Expected {expected!r}, found {self.tokenizer.current_token!r}"
            )
        self._advance()

    def _eat_identifier(self):
        if self.tokenizer.token_type != "IDENTIFIER":
            raise SyntaxError(f"Expected identifier, found {self.tokenizer.current_token!r}")
        value = self.tokenizer.current_token
        self._advance()
        return value

    def _parse_type(self, allow_void=False):
        token = self.tokenizer.current_token
        valid = {"int", "char", "boolean"}
        if self.tokenizer.token_type == "IDENTIFIER" or token in valid or (allow_void and token == "void"):
            self._advance()
            return token
        raise SyntaxError(f"Invalid type: {token!r}")

    def _unique_label(self, prefix):
        self.label_counter += 1
        return f"{prefix}_{self.label_counter}"

    def _map_segment(self, kind):
        mapping = {"STATIC": "static", "FIELD": "this", "ARG": "argument", "VAR": "local"}
        if kind not in mapping:
            raise SyntaxError("Undefined variable or unsupported symbol kind")
        return mapping[kind]

    def _push_variable(self, name):
        kind = self.sym_table.kind_of(name)
        if kind is None:
            raise SyntaxError(f"Undefined variable: {name}")
        self.vm.write_push(self._map_segment(kind), self.sym_table.index_of(name))

    def _pop_variable(self, name):
        kind = self.sym_table.kind_of(name)
        if kind is None:
            raise SyntaxError(f"Undefined variable: {name}")
        self.vm.write_pop(self._map_segment(kind), self.sym_table.index_of(name))

    def compile_class(self):
        if self.tokenizer.current_token is None:
            self._advance()
        self._eat("class")
        self.class_name = self._eat_identifier()
        self._eat("{")

        while self.tokenizer.current_token in ("static", "field"):
            self.compile_class_var_dec()

        while self.tokenizer.current_token in ("constructor", "function", "method"):
            self.compile_subroutine()

        self._eat("}")

    def compile_class_var_dec(self):
        kind = self.tokenizer.current_token.upper()
        self._advance()
        type_ = self._parse_type()
        while True:
            name = self._eat_identifier()
            self.sym_table.define(name, type_, kind)
            if self.tokenizer.current_token != ",":
                break
            self._advance()
        self._eat(";")

    def compile_var_dec(self):
        self._eat("var")
        type_ = self._parse_type()
        while True:
            name = self._eat_identifier()
            self.sym_table.define(name, type_, "VAR")
            if self.tokenizer.current_token != ",":
                break
            self._advance()
        self._eat(";")

    def compile_subroutine(self):
        sub_type = self.tokenizer.current_token
        self.sym_table.start_subroutine()
        self._advance()
        self._parse_type(allow_void=True)
        sub_name = self._eat_identifier()
        full_name = f"{self.class_name}.{sub_name}"

        self._eat("(")
        if sub_type == "method":
            self.sym_table.define("this", self.class_name, "ARG")
        self.compile_parameter_list()
        self._eat(")")
        self._eat("{")

        while self.tokenizer.current_token == "var":
            self.compile_var_dec()

        self.vm.write_function(full_name, self.sym_table.var_count("VAR"))

        if sub_type == "constructor":
            self.vm.write_push("constant", self.sym_table.var_count("FIELD"))
            self.vm.write_call("Memory.alloc", 1)
            self.vm.write_pop("pointer", 0)
        elif sub_type == "method":
            self.vm.write_push("argument", 0)
            self.vm.write_pop("pointer", 0)

        self.compile_statements()
        self._eat("}")

    def compile_parameter_list(self):
        if self.tokenizer.current_token == ")":
            return
        while True:
            type_ = self._parse_type()
            name = self._eat_identifier()
            self.sym_table.define(name, type_, "ARG")
            if self.tokenizer.current_token != ",":
                break
            self._advance()

    def compile_statements(self):
        dispatch = {
            "let": self.compile_let,
            "if": self.compile_if,
            "while": self.compile_while,
            "do": self.compile_do,
            "return": self.compile_return
        }
        while self.tokenizer.current_token in dispatch:
            dispatch[self.tokenizer.current_token]()

    def compile_let(self):
        self._eat("let")
        name = self._eat_identifier()
        is_array = self.tokenizer.current_token == "["

        if is_array:
            self._push_variable(name)
            self._eat("[")
            self.compile_expression()
            self._eat("]")
            self.vm.write_arithmetic("add")

        self._eat("=")
        self.compile_expression()
        self._eat(";")

        if is_array:
            # Stack before this sequence: [..., target-address, value]
            self.vm.write_pop("temp", 0)
            self.vm.write_pop("pointer", 1)
            self.vm.write_push("temp", 0)
            self.vm.write_pop("that", 0)
        else:
            self._pop_variable(name)

    def compile_if(self):
        self._eat("if")
        true_label = self._unique_label("IF_TRUE")
        false_label = self._unique_label("IF_FALSE")
        end_label = self._unique_label("IF_END")
        self._eat("(")
        self.compile_expression()
        self._eat(")")
        self.vm.write_if(true_label)
        self.vm.write_goto(false_label)
        self.vm.write_label(true_label)
        self._eat("{")
        self.compile_statements()
        self._eat("}")

        if self.tokenizer.current_token == "else":
            self.vm.write_goto(end_label)
            self.vm.write_label(false_label)
            self._eat("else")
            self._eat("{")
            self.compile_statements()
            self._eat("}")
            self.vm.write_label(end_label)
        else:
            self.vm.write_label(false_label)

    def compile_while(self):
        self._eat("while")
        exp_label = self._unique_label("WHILE_EXP")
        end_label = self._unique_label("WHILE_END")
        self.vm.write_label(exp_label)
        self._eat("(")
        self.compile_expression()
        self._eat(")")
        self.vm.write_arithmetic("not")
        self.vm.write_if(end_label)
        self._eat("{")
        self.compile_statements()
        self._eat("}")
        self.vm.write_goto(exp_label)
        self.vm.write_label(end_label)

    def compile_do(self):
        self._eat("do")
        self.compile_subroutine_call()
        self._eat(";")
        self.vm.write_pop("temp", 0)  # discard the returned value

    def compile_return(self):
        self._eat("return")
        if self.tokenizer.current_token == ";":
            self.vm.write_push("constant", 0)
        else:
            self.compile_expression()
        self._eat(";")
        self.vm.write_return()

    def compile_expression(self):
        self.compile_term()
        while self.tokenizer.current_token in (
            "+", "-", "*", "/", "&", "|", "<", ">", "="
        ):
            op = self.tokenizer.current_token
            self._advance()
            self.compile_term()
            if op in self.BINARY_OPS:
                self.vm.write_arithmetic(self.BINARY_OPS[op])
            elif op == "*":
                self.vm.write_call("Math.multiply", 2)
            elif op == "/":
                self.vm.write_call("Math.divide", 2)

    def compile_term(self):
        token = self.tokenizer.current_token
        token_type = self.tokenizer.token_type

        if token_type == "INT_CONST":
            self.vm.write_push("constant", self.tokenizer.int_val())
            self._advance()
        elif token_type == "STRING_CONST":
            value = self.tokenizer.string_val()
            self.vm.write_push("constant", len(value))
            self.vm.write_call("String.new", 1)
            for char in value:
                self.vm.write_push("constant", ord(char))
                self.vm.write_call("String.appendChar", 2)
            self._advance()
        elif token in ("true", "false", "null", "this"):
            self._advance()
            if token == "true":
                self.vm.write_push("constant", 0)
                self.vm.write_arithmetic("not")
            elif token in ("false", "null"):
                self.vm.write_push("constant", 0)
            else:
                self.vm.write_push("pointer", 0)
        elif token == "(":
            self._eat("(")
            self.compile_expression()
            self._eat(")")
        elif token in self.UNARY_OPS:
            op = token
            self._advance()
            self.compile_term()
            self.vm.write_arithmetic(self.UNARY_OPS[op])
        elif token_type == "IDENTIFIER":
            name = self._eat_identifier()
            if self.tokenizer.current_token == "[":
                self._push_variable(name)
                self._eat("[")
                self.compile_expression()
                self._eat("]")
                self.vm.write_arithmetic("add")
                self.vm.write_pop("pointer", 1)
                self.vm.write_push("that", 0)
            elif self.tokenizer.current_token in ("(", "."):
                self.compile_subroutine_call(first_name=name)
            else:
                self._push_variable(name)
        else:
            raise SyntaxError(f"Invalid term: {token!r}")

    def compile_subroutine_call(self, first_name=None):
        name = first_name if first_name is not None else self._eat_identifier()
        n_args = 0

        if self.tokenizer.current_token == ".":
            self._advance()
            sub_name = self._eat_identifier()
            kind = self.sym_table.kind_of(name)
            if kind is not None:
                self._push_variable(name)
                n_args = 1
                class_or_var_type = self.sym_table.type_of(name)
                full_name = f"{class_or_var_type}.{sub_name}"
            else:
                full_name = f"{name}.{sub_name}"
        else:
            # Unqualified call is a method on the current object.
            self.vm.write_push("pointer", 0)
            n_args = 1
            full_name = f"{self.class_name}.{name}"

        self._eat("(")
        n_args += self.compile_expression_list()
        self._eat(")")
        self.vm.write_call(full_name, n_args)

    def compile_expression_list(self):
        count = 0
        if self.tokenizer.current_token != ")":
            while True:
                self.compile_expression()
                count += 1
                if self.tokenizer.current_token != ",":
                    break
                self._advance()
        return count
