# DCOM setup for Dewesoft
from win32com.client import Dispatch
import pythoncom
# Math
import numpy as np
# General
import sys
from tqdm.notebook import tqdm



class DSSetup:
    def __init__(self, setup_file_path):
        """
        Class for connecting and configuring Dewesoft measurement acquisition hardware.
        This class handles the initialization of Dewesoft, loading of setup files, and configuration of measurement parameters for impact testing.
        

        PARAMETERS:
        # Dewesoft connection params
        :param setup_file_path: str - Path to the setup file (.dxs file).
        

        # Measurement setup params
        :param chn_names: list, optional - List of channel names to be used in the measurement.
        :param impact_names: list, optional - List of impact names.


        ATTRIBUTES: TODO: Preglej!
        dw: Dispatch object for Dewesoft application.
        channels: List of used channels in the measurement.
        chn_dict: Dictionary mapping channel indices to channel names.
        sensor_dict: Dictionary containing sensor details such as name, sensitivity, and range.
        force_ind: Index of the excitation force channel.
        acc_indices: List of indices for response channels.
        chn_names: List of channel names used in the measurement.
        impact_names: List of impact names.
        sampling_rate: Sampling rate of the data acquisition.
        samples_per_channel: Number of samples per channel.
        acquisition_time: Total acquisition time.

        """
        # TODO: Dodaj tqdm za napredek inicializacije
        # ACQUISITION SYSTEM
        self.acq_name = 'Dewesoft'

        # Initialization progress bar
        init_pbar = tqdm(total=5, desc='Initializing Dewesoft', bar_format='{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt}')
        # INITIALIZE DEWESOFT
        self.dw = Dispatch("Dewesoft.App")
        sys.stdout.flush() # flush stdout buffer
        self.dw.init()
        self.dw.Enabled = 1
        self.dw.Visible = 1
        init_pbar.update(1)
        init_pbar.set_description('Loading setup file')

        # LOAD SETUP FILE
        try:
            self.dw.LoadSetup(setup_file_path)
        except pythoncom.com_error:
            self.dw.Stop()
            self.dw.LoadSetup(setup_file_path)
        init_pbar.update(1)
        init_pbar.set_description('Navigating to measurement screen')
        
        # GO TO MEASUREMENT SCREEN - IMPACT TESTING
        self.go_to_meas_window()
        init_pbar.update(1)
        init_pbar.set_description('Starting measurement')
        
        # START MEASUREMENT
        self.dw.Start()
        init_pbar.update(1)
        init_pbar.set_description('Reading channel and sensor data')
        
        # READ CHANNEL AND SENSOR DETAILS
        self.channels = [self.dw.Data.UsedChannels.Item(_) for _ in range(self.dw.Data.UsedChannels.Count)]
        self.chn_dict = {ind_:chn_.Name for ind_, chn_ in enumerate(self.channels)}
        self.sensor_dict = {ind_:{'Name': chn_.Name, 'Sensitivity': chn_.Scale**-1, 'RangeMaxValue': chn_.TypicalMaxValue, 'RangeMinValue': chn_.TypicalMinValue} for ind_, chn_ in enumerate(self.channels) if 'AI' in chn_.Name}
        init_pbar.update(1)
        init_pbar.colour = 'green'
        init_pbar.set_description('Connection to Dewesoft established')
        
        # GET INDICES FOR CHANNELS OF INTEREST
        self.force_ind = [ind_ for ind_, value_ in self.chn_dict.items() if 'Exc' in value_ and 'Scope' in value_][0]
        self.acc_indices = [ind_ for ind_, value_ in self.chn_dict.items() if 'Res' in value_ and 'Scope' in value_]
        
        # ACQUITISION PROPERTIES
        self.sampling_rate = self.dw.Data.SampleRate
        self.samples_per_channel = None
        self.acquisition_time = None

    def go_to_meas_window(self):
        """
        Method for navigating to the measurement screen in DewesoftX.
        """
        self.dw.SetMainToolBar('Measure', 'Custom')
        self.dw.SetInstrument(2)
        self.dw.SetScreenIndex(1)

    def close_connection(self):
        """
        Method for closing the connection to Dewesoft.
        """
        self.dw.Stop()
        self.dw = None
    
    def get_impact(self, imp):
        """
        Method for detecting the impact and acquiring the impact data.
        """
        self.dw.Start()

        if self.dw.IsSetupMode:
            self.go_to_meas_window()

        current_no_imp = int(self.channels[4].GetScaledData()[0])
        while True:
            if current_no_imp != int(self.channels[4].GetScaledData()[0]):
                if imp==0:
                    self.samples_per_channel = len(self.channels[self.force_ind].GetScaledDataDoubleEx(0,1))
                    self.acquisition_time = self.samples_per_channel / self.sampling_rate
                # Save measurement data - force is always stored at index 0 for each impact
                imp_measurement_data = np.array(self.channels[self.force_ind].GetScaledDataDoubleEx(0,1))[None,:]
                for acc_ in np.array(self.channels)[self.acc_indices]:
                    imp_measurement_data = np.concatenate([imp_measurement_data, np.array(acc_.GetScaledDataDoubleEx(0,1))[None,:]])
                break
            else:
                pass
        self.dw.Stop()
        return imp_measurement_data