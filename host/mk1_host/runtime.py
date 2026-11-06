"""Bounded session loop; source and backend are supplied, never selected here."""
import time

def run_session(controller, reader, seconds, max_age_us, read_budget=32,
                clock_ns=time.monotonic_ns, sleeper=time.sleep, on_ready=None):
    if not 0 < seconds <= 60 or type(max_age_us) is not int or max_age_us <= 0 or not 1 <= read_budget <= 128:
        raise ValueError('Invalid bounded session limits')
    result = {'reports': 0, 'max_queue_age_us': 0, 'reason': None,
              'clean_stop': False, 'reader_exited': False, 'started': False}
    try:
        reader.start()
        start = clock_ns()
        generation = controller.start(start//1000)
        result['started'] = True
        if on_ready is not None:
            on_ready()
        deadline = start+int(seconds*1e9)
        while clock_ns() < deadline:
            fault = reader.status()['fault']
            if fault:
                result['reason'] = fault
                break
            for _ in range(read_budget):
                item = reader.read()
                if item is None:
                    break
                sequence, stamp, data = item
                now = clock_ns()
                age = (now-stamp)//1000
                if age < 0 or age > max_age_us:
                    result['reason'] = 'Input queue age outside allowed range'
                    break
                result['max_queue_age_us'] = max(result['max_queue_age_us'], age)
                # Native timing follows parent processing time; original child
                # arrival is retained only for the age guard. Never feed old
                # timestamps behind an already-polled native clock watermark.
                controller.feed(data, now//1000, generation, sequence)
                result['reports'] += 1
                if controller.phase != 'running':
                    result['reason'] = controller.reason or controller.phase
                    break
            if result['reason']:
                break
            controller.advance(clock_ns()//1000)
            if controller.phase != 'running':
                result['reason'] = controller.reason or controller.phase
                break
            sleeper(.001)
        if result['reason'] is None:
            result['reason'] = 'duration complete'
    except KeyboardInterrupt:
        result['reason'] = 'operator interrupt'
    except Exception as error:
        result['reason'] = f'{type(error).__name__}: {error}'
    finally:
        try:
            result['clean_stop'] = controller.stop(clock_ns()//1000)
        except Exception as error:
            result['cleanup_error'] = str(error)
        try:
            result['reader_exited'] = reader.close()
        except Exception as error:
            result['reader_close_error'] = str(error)
        result['final_status'] = controller.status()
    result['ok'] = (result['reason'] in ('duration complete', 'operator interrupt') and
                    result['clean_stop'] and result['reader_exited'])
    return result
