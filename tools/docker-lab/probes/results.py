"""Record visual-probe cleanup without hiding a failed workload."""


def record_cleanup(result, *, window_closed, running_children):
    result['cleanup'] = {'window_closed': window_closed,
                         'running_children': running_children}
    if not window_closed or running_children:
        result['completed'] = False
