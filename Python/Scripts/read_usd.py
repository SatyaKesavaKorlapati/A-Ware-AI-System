from pxr import Usd

stage = Usd.Stage.Open(
    r"D:\RAJU\rs\IssacSim\Collected_Warehouse\Warehouse.usd"
)

def print_tree(prim, indent=0):
    print("  " * indent + str(prim.GetPath()))
    for child in prim.GetChildren():
        print_tree(child, indent + 1)

print_tree(stage.GetPseudoRoot())