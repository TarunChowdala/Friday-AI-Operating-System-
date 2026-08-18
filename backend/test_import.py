import multiprocessing
import sys

def worker():
    print("In worker process", flush=True)
    print("sys.path:", sys.path, flush=True)
    try:
        from duckduckgo_search import DDGS
        print("SUCCESSFULLY IMPORTED DDGS in worker", flush=True)
    except Exception as e:
        print("FAILED TO IMPORT DDGS in worker:", type(e), e, flush=True)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("In main process", flush=True)
    print("sys.path:", sys.path, flush=True)
    try:
        from duckduckgo_search import DDGS
        print("SUCCESSFULLY IMPORTED DDGS in main", flush=True)
    except Exception as e:
        print("FAILED TO IMPORT DDGS in main:", type(e), e, flush=True)
    
    multiprocessing.set_start_method("spawn")
    p = multiprocessing.Process(target=worker)
    p.start()
    p.join()
