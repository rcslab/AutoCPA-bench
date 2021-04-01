import numpy as np

class MutilateParser:
    def _parse_mut_stdout(self, std_out):
        succ_qps = False
        succ_read = False
        table = [None, "avg", "std", "min", "5th", "10th", "50th", "90th", "95th", "99th"]
        table_legacy = [None, "avg", "std", "min", "5th", "10th", "90th", "95th", "99th"]
        for line in output.splitlines():
            if line.find("Total QPS") != -1:
                spl = line.split()
                if len(spl) == 7:
                    ret.qps = float(spl[3])
                    succ_qps = True
                else:
                    break
            elif line.find("read") != -1:
                spl = line.split()
                if len(spl) == 10:
                    for i in range(1, len(spl)):
                        ret.lat[table[i]] = float(spl[i])
                    succ_read = True
                elif len(spl) == 9:
                    for i in range(1, len(spl)):
                        ret.lat[table_legacy[i]] = float(spl[i])
                    succ_read = True
                else:
                    break
        
        if not (succ_qps and succ_read):
            raise Exception("Failed to parse data")

        return ret

    # generate mutilate output format
    @staticmethod
    def build_stdout(lat_arr, qps):
        output = '{0: <10}'.format('#type') + '{0: >10}'.format('avg') + '{0: >10}'.format('std') + \
                        '{0: >10}'.format('min') + '{0: >10}'.format('5th') + '{0: >10}'.format('10th') + \
                        '{0: >10}'.format('50th') + '{0: >10}'.format('90th')  + '{0: >10}'.format('95th') + '{0: >10}'.format('99th') + "\n"
        
        output += '{0: <10}'.format('read') + '{0: >10}'.format("{:.1f}".format(np.mean(lat_arr))) + ' ' + \
                        '{0: >10}'.format("{:.1f}".format(np.std(lat_arr))) + ' ' + \
                        '{0: >10}'.format("{:.1f}".format(np.min(lat_arr))) + ' ' + \
                        '{0: >10}'.format("{:.1f}".format(np.percentile(lat_arr, 5))) + ' ' + \
                        '{0: >10}'.format("{:.1f}".format(np.percentile(lat_arr, 10))) + ' ' + \
                        '{0: >10}'.format("{:.1f}".format(np.percentile(lat_arr, 50))) + ' ' + \
                        '{0: >10}'.format("{:.1f}".format(np.percentile(lat_arr, 90))) + ' ' + \
                        '{0: >10}'.format("{:.1f}".format(np.percentile(lat_arr, 95))) + ' ' + \
                        '{0: >10}'.format("{:.1f}".format(np.percentile(lat_arr, 99))) + ' ' + "\n" \

        output += "\n" + "Total QPS = " + "{:.1f}".format(qps) + " (0 / 0s)"

        return output

    def __init__(self, std_out):
        ret = _parse_mut_stdout(std_out)
        self.qps = ret.qps
        self.lat = ret.lat

class DismemberParser:
    def __init__(self, sample : [str]):
        self.lat = []
        for line in sample:
            spl = line.split(' ')
            if len(spl) != 2:
                raise Exception(f"Invalid line: {line}")
            self.lat.append(int(spl[1]))
            self.qps = int(spl[0])
