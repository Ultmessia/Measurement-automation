from scipy import *
from resonator_tools.circuit import notch_port
from matplotlib import pyplot as plt
from scipy.signal import savgol_filter

class ResonatorDetector():

    def __init__(self, frequencies, s_data, plot = True, fast = False):

        self._freqs = frequencies
        self._s_data = s_data
        self._plot = plot
        self._port = notch_port(frequencies, s_data)
        # self._s_data_filtered = (savgol_filter(real(self._s_data), 21, 2)\
        #                         + 1j*savgol_filter(imag(self._s_data), 21, 2))
        # self._filtered_port = notch_port(frequencies, self._s_data_filtered)
        self._fast = fast

    def detect(self):

        frequencies, sdata = self._freqs, self._s_data

        if not self._fast:
            result = self._fit()
        else:
            amps = abs(self._s_data)
            phas = angle(self._s_data)
            min_idx = argmin(amps)
            result = frequencies[min_idx], min(amps), phas[min_idx]

        if result is not None:
            if self._plot:
                self._port.plotall()
            return result



    def _fit(self):

        scan_range = self._freqs[-1]-self._freqs[0]

        try:
            self._port.autofit()
        except Exception as e:
            print(e)
            # print(self._s_data, self._freqs)
            # exit()
            return None

        if not self._freqs[0] < self._port.fitresults["fr"] < self._freqs[-1]\
            or self._port.fitresults["Ql"]>20000:
            # fit failed
            return None


        min_idx = argmin(abs(self._s_data))
        expected_frequency = self._freqs[min_idx]
        expected_amplitude = abs(self._s_data)[min_idx]

        fit_min_idx = argmin(abs(self._port.z_data_sim))
        fit_frequency = self._freqs[fit_min_idx]
        fit_amplitude = min(abs(self._port.z_data_sim))
        fit_angle = angle(self._port.z_data_sim)[fit_min_idx]
        res_width = fit_frequency/self._port.fitresults["Ql"]

        if abs(fit_frequency-expected_frequency)<0.1*res_width and \
            abs(fit_amplitude-expected_amplitude)<5*expected_amplitude:
            return fit_frequency, fit_amplitude, fit_angle
        else:
            pass
            # print(fit_frequency, expected_frequency)
