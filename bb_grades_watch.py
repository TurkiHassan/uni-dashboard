"""Compatibility entry point for private Blackboard grade synchronization."""
from blackboard_review import main, run_sync, grade_value, clean, ensure_login

if __name__ == '__main__':
    raise SystemExit(main())
