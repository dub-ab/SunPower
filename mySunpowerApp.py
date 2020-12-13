import requests
import json
from  influxdb import InfluxDBClient
import config
import time
from time import strftime
import smtplib
from email.message import EmailMessage


static_time = 0        # the base time
length_of_timer = 60   # in seconds 
kounter = 0            # keep track of the number of times through the length_of_timer loop
known_inverters = [    # the last 8 characters of the serial number for my inverters
    '08088935', 
    '08088938', 
    '08097339', 
    '08097345', 
    '08097454', 
    '08099583', 
    '08100391', 
    '10041974', 
    '10042927', 
    '10049090', 
    '10050996', 
    '10051227', 
    '10051706', 
    '10059735', 
    '10059833'
]
report = EmailMessage() # the email report object
report["To"] = config.smtp_receivers
report["From"] = config.smtp_sender

def send_report(report_object):
    """
        send an email notification using the message object  

        Argument: an email.message.Message object
    """
    try:
        with smtplib.SMTP_SSL(config.smtp_server, 465) as smtp:
            smtp.login(config.smtp_user, config.smtp_password)
            smtp.send_message(report_object)
    except smtplib.SMTPException as e:
        print(f"a SMTP protocol exception occurred!\n {str(e)}\n")

def human_time_format(c_time):
    """
        a function to string format UNIX time (since epoch) into a human readable form  
        Argument:  
        c_time (float): the current UNIX time 
    
        a function to string format UNIX time (since epoch) into a human readable form  
        Argument:  
        c_time (float): the current UNIX time 

        Return:  
        a string representation of the current UNIX time
    """
    return strftime("%a, %d %b %Y %H:%M:%S", time.localtime(c_time))

def influxdb_connect(db='sunpower'):
    """
        open a new connection to the InfluxDB  
        Argument:
            db (string): name of the database for which you wish to connect (default: 'sunpower')  
            this connection uses the authentication creditionals 'username' and 'password'
        Returns:  
            InfluxDBClient: an InfluxDB client connected to the named InfluxDB database  
            otherwise a failure message
    """
    try:
        client = InfluxDBClient(host=f"{config.dev_server}", port=8086, 
            username=config.influx_username, password=config.influx_password)
        client.switch_database(db)
        return client
    except:
        print(f"could not connect to database: ")

def poll_the_PVS():
    """ 
        this function will make the api call to the sunpower console and
        return a list of influx 
    """
    
    # the sunpower console
    url = f"http://{config.dev_server}:8080/cgi-bin/dl_cgi?Command=DeviceList"
        
    # the influxdb payload        
    payload = []
            
    # gather the response from the request made to the sunpower console  
    try:
        response = requests.request("GET", url)
    
        if response.status_code == 200:
            # success! Do work
            content_json = response.json()
            
            for device in content_json["devices"]:
                if device["DEVICE_TYPE"] == "PVS":
                    payload.append({
                        'measurement' : 'Supervisor',
                        'tags' : {
                            'serial' : device["SERIAL"],     
                            'model' : device["MODEL"],
                            'hwver' : device["HWVER"],   
                            'swver' : device["SWVER"],  
                            'device_type' : device["DEVICE_TYPE"]
                        },
                        'fields' : {
                            'dl_uptime' : float(device["dl_uptime"]),              # number of seconds the system has been running
                            'dl_cpu_load' : float(device["dl_cpu_load"]),          # 1-minute load average
                            'dl_mem_used' : float(device["dl_mem_used"]),          # amount of memory used, in KiB (assumed 1GiB of RAM)
                            'dl_flash_avail' : float(device["dl_flash_avail"]),    # amount of free space, in KiB (assumed 1GiB of storage)
                            'datatime' : device["DATATIME"],
                            'curtime' : device["CURTIME"]    
                        }
                    })  
                elif device["DEVICE_TYPE"] =="Power Meter" and device["CAL0"] == "50":
                    # The calibration-reference CT sensor size (50A for production, 100A for consumption)
                    payload.append({
                        'measurement' : 'Production',
                        'tags' : {
                            'serial' : device["SERIAL"],
                            'model' : device["MODEL"],
                            'desc' : device["DESCR"],
                            'device_type' : device["DEVICE_TYPE"],
                            'swver' : device["SWVER"], 
                            'type' : device["TYPE"]
                        },  
                        'fields' : {
                            'ct_scl_fctr' : device["ct_scl_fctr"],                             # The CT sensor size (50A for production, 100A/200A for consumption)
                            'total_net_energy_kwh' : float(device["net_ltea_3phsum_kwh"]),     # Total Net Energy (kilowatt-hours)
                            'p_3phsum_kw' : float(device["p_3phsum_kw"]),                      # Average real power (kilowatts)
                            'q_3phsum_kvar' : float(device["q_3phsum_kvar"]),                  # Reactive power (kilovolt-amp-reactive)
                            's_3phsum_kva' : float(device["s_3phsum_kva"]),                    # Apparent power (kilovolt-amp)
                            'tot_pf_rto' : float(device["tot_pf_rto"]),                        # Power Factor ratio (real power / apparent power)
                            'freq_hz' : float(device["freq_hz"]),                              # Operating Frequency
                            'datatime' : device["DATATIME"],
                            'curtime' : device["CURTIME"]                                
                        }
                    })
                elif device["DEVICE_TYPE"] =="Power Meter" and device["CAL0"] == "100":
                    # The calibration-reference CT sensor size (50A for production, 100A for consumption)   
                    payload.append({
                        'measurement' : 'Consumption',
                        'tags' : {
                            'serial' : device["SERIAL"],
                            'model' : device["MODEL"],
                            'desc' : device["DESCR"],
                            'device_type' : device["DEVICE_TYPE"],
                            'swver' : device["SWVER"], 
                            'type' : device["TYPE"]
                        },  
                        'fields' : {
                            'ct_scl_fctr' : device["ct_scl_fctr"],                              # The CT sensor size (50A for production, 100A/200A for consumption)
                            'total_net_energy_kwh' : float(device["net_ltea_3phsum_kwh"]),     # Total Net Energy (kilowatt-hours)
                            'p_3phsum_kw' : float(device["p_3phsum_kw"]),                      # Average real power (kilowatts)
                            'q_3phsum_kvar' : float(device["q_3phsum_kvar"]),                  # Reactive power (kilovolt-amp-reactive)
                            's_3phsum_kva' : float(device["s_3phsum_kva"]),                    # Apparent power (kilovolt-amp)
                            'tot_pf_rto' : float(device["tot_pf_rto"]),                        # Power Factor ratio (real power / apparent power)
                            'freq_hz' : float(device["freq_hz"]),                              # Operating Frequency
                            'datatime' : device["DATATIME"],
                            'curtime' : device["CURTIME"]                                
                        }
                    })            
                else:
                    # It must be an inverter
                    # Inverters have various state_descriptions to test 
                    if device["STATEDESCR"] == "Working":
                        payload.append({
                            'measurement' : 'Inverters',
                            'tags' : {
                                'serial' : device["SERIAL"], 
                                'serial_short' : device["SERIAL"][-8:],
                                'type' : device["TYPE"],
                                'state' : device["STATE"],
                                'model' : device["MODEL"],
                                'desc' : device["DESCR"],
                                'device_type' : device["DEVICE_TYPE"],
                                'swver' : device["SWVER"], 
                                'mod_sn' : device["MOD_SN"]
                            },
                            'fields' : {   
                                'freq_hz' : float(device["freq_hz"]),                  # Operating Frequency
                                'i_3phsum_a' : float(device["i_3phsum_a"]),            # AC Current (amperes)
                                'i_mppt1_a' : float(device["i_mppt1_a"]),              # DC Current (amperes)
                                'ltea_3phsum_kwh' : float(device["ltea_3phsum_kwh"]),  # Total energy (kilowatt-hours)
                                'p_3phsum_kw' : float(device["p_3phsum_kw"]),          # AC Power (kilowatts)
                                'p_mpptsum_kw' : float(device["p_mpptsum_kw"]),        # DC Power (kilowatts)
                                't_htsnk_degc' : float(device["t_htsnk_degc"]),        # Heatsink temperature (degrees Celsius)
                                'v_mppt1_v' : float(device["v_mppt1_v"]),              # DC Voltage (volts)
                                'vln_3phavg_v' : float(device["vln_3phavg_v"]),        # AC Voltage (volts)
                                'datatime' : device["DATATIME"],
                                'curtime' : device["CURTIME"],
                                'statedescr' : device["STATEDESCR"]   
                        }
                    })
                    else:
                        # the inverter state_description does not say 'working'
                        payload.append({
                            'measurement' : 'Inverters',
                            'tags' : {
                                'serial' : device["SERIAL"], 
                                'serial_short' : device["SERIAL"][-8:],
                                'type' : device["TYPE"],
                                'state' : device["STATE"],
                                'model' : device["MODEL"],
                                'desc' : device["DESCR"],
                                'device_type' : device["DEVICE_TYPE"],
                                'swver' : device["SWVER"], 
                                'mod_sn' : device["MOD_SN"]
                            },
                            'fields' : {   
                                'freq_hz' : 0.0,          
                                'i_3phsum_a' : 0.0,       
                                'i_mppt1_a' : 0.0,        
                                'ltea_3phsum_kwh' : 0.0,  
                                'p_3phsum_kw' : 0.0,      
                                'p_mpptsum_kw' : 0.0,     
                                't_htsnk_degc' : 0.0,     
                                'v_mppt1_v' : 0.0,        
                                'vln_3phavg_v' : 0.0,
                                'curtime' : device["CURTIME"],
                                'statedescr' : device["STATEDESCR"]   
                            }
                        })
            return payload
        
        elif response.status_code == 404:
            print("the server reported a 404 status code.")
    
    except requests.exceptions.RequestException as e:
        print(f"a requests error occured: {str(e)}")

static_time = time.time()
human_time = human_time_format(static_time)
print(f"""
+++
  current epoch time is: {static_time}
  thats: {human_time} for humans.
  the sunpower monitor is running. time to poll the PVS...
  
  --> use 'ctrl+c' to exit
""" )

try:
    while True:      

        try:   
            results = poll_the_PVS()
            if results != None:
                my_connection = influxdb_connect('sunpower')   
                my_connection.write_points(results)
        except InterruptedError as e:
            print(f"error code {e}")
        except Exception as e:
            current_time = time.time()
            print(f"at {human_time_format(current_time)} something went wrong. {str(e)}\n")
        finally:
            my_connection.close()

        kounter += 1
        if kounter == (3600 / length_of_timer):
            # print("one hour has elapsed. time to send the email")
            # TODO must decide if the database has been down for an hour or
            # bad inverters being reported.
            kounter = 0

        time.sleep(length_of_timer)

except KeyboardInterrupt as e:
    print(f"""
  ***** the sunpower monitor has exited by request *****
+++  
    """)
    import sys
    sys.exit() 




