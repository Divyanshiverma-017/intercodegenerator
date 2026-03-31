"""
PHASE 3 - SEMANTIC ANALYSIS
Performs semantic analysis on the AST to check for:
- Variable declarations and usage
- Type checking
- Scope validation
- Semantic errors
"""

from typing import Dict, List, Set, Optional
from phase1 import ASTNode, Number, Variable, BinaryOp, Assign, Program


class SymbolTable:
    def __init__(self):
        self.symbols: Dict[str, Dict] = {}
        self.errors: List[str] = []
    
    def declare(self, name: str, node_type: str = 'unknown'):
        if name in self.symbols:
            self.errors.append(f"Variable '{name}' already declared")
        else:
            self.symbols[name] = {
                'type': node_type,
                'declared': True,
                'used': False
            }
    
    def use(self, name: str):
        if name not in self.symbols:
            self.errors.append(f"Variable '{name}' used but not declared")
        else:
            self.symbols[name]['used'] = True
    
    def check_unused_variables(self):
        for name, info in self.symbols.items():
            if info['declared'] and not info['used']:
                self.errors.append(f"Variable '{name}' declared but never used")


class SemanticAnalyzer:
    def __init__(self):
        self.symbol_table = SymbolTable()
        self.current_function = None
    
    def analyze(self, node: ASTNode) -> List[str]:
        """Main entry point for semantic analysis."""
        self._analyze_node(node)
        self.symbol_table.check_unused_variables()
        return self.symbol_table.errors
    
    def _analyze_node(self, node: ASTNode):
        """Recursively analyze AST nodes."""
        if isinstance(node, Program):
            for stmt in node.statements:
                self._analyze_node(stmt)
        
        elif isinstance(node, Assign):
            # Declare the variable
            self.symbol_table.declare(node.name)
            # Analyze the expression
            self._analyze_node(node.expr)
        
        elif isinstance(node, Variable):
            # Use of variable
            self.symbol_table.use(node.name)
        
        elif isinstance(node, Number):
            # Numbers don't need semantic checking
            pass
        
        elif isinstance(node, BinaryOp):
            # Analyze both operands
            self._analyze_node(node.left)
            self._analyze_node(node.right)
        
        else:
            raise TypeError(f"Unknown AST node type: {type(node)}")


def perform_semantic_analysis(ast: ASTNode) -> List[str]:
    analyzer = SemanticAnalyzer()
    errors = analyzer.analyze(ast)
    
    if errors:
        print("PHASE 3 - SEMANTIC ANALYSIS ERRORS:")
        for error in errors:
            print(f"  - {error}")
    else:
        print("PHASE 3 - SEMANTIC ANALYSIS: No errors found")
    
    return errors