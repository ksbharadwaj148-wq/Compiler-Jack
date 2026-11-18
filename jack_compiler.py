import sys
from pathlib import Path

try:  # Supports both `python -m src.jack_compiler` and direct script execution.
    from src.jack_tokenizer import JackTokenizer
    from src.symbol_table import SymbolTable
    from src.vm_writer import VMWriter
    from src.compilation_engine import CompilationEngine
except ImportError:
    from jack_tokenizer import JackTokenizer
    from symbol_table import SymbolTable
    from vm_writer import VMWriter
    from compilation_engine import CompilationEngine


def compile_file(jack_path, output_dir):
    jack_path = Path(jack_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{jack_path.stem}.vm"

    tokenizer = JackTokenizer(jack_path)
    symbol_table = SymbolTable()
    vm_writer = VMWriter(output_path)
    try:
        engine = CompilationEngine(tokenizer, symbol_table, vm_writer)
        engine.compile_class()
        if tokenizer.current_token is not None:
            raise SyntaxError(f"Unexpected token after class: {tokenizer.current_token}")
    finally:
        vm_writer.close()

    print(f"Compiled: {jack_path.name} -> {output_path}")


def compile_directory(input_dir, output_dir):
    input_dir = Path(input_dir)
    jack_files = sorted(input_dir.glob("*.jack"))
    if not jack_files:
        raise FileNotFoundError(f"No .jack files found in {input_dir}")
    for jack_file in jack_files:
        compile_file(jack_file, output_dir)


def main():
    if len(sys.argv) not in (2, 3):
        print("Usage: python -m src.jack_compiler <input.jack | input_dir> [output_dir]")
        raise SystemExit(2)

    input_path = Path(sys.argv[1])
    output_dir = Path(sys.argv[2]) if len(sys.argv) == 3 else Path("output")

    if input_path.is_file() and input_path.suffix.lower() == ".jack":
        compile_file(input_path, output_dir)
    elif input_path.is_dir():
        compile_directory(input_path, output_dir)
    else:
        raise FileNotFoundError("Input must be a .jack file or a directory containing .jack files.")


if __name__ == "__main__":
    main()
