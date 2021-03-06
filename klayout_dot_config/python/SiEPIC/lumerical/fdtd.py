'''
################################################################################
#
#  SiEPIC-Tools
#  
################################################################################

Component simulations using Lumerical FDTD, to generate Compact Models

- component_simulation: single component simulation

usage:

import SiEPIC.lumerical.fdtd


################################################################################
'''

import sys
if 'pya' in sys.modules: # check if in KLayout
  import pya


def run_FDTD(verbose=False):
  from . import load_lumapi
  from .. import _globals
  lumapi = _globals.LUMAPI
  if not lumapi:
    print("SiEPIC.lumerical.interconnect.run_FDTD: lumapi not loaded; reloading load_lumapi.")
    import sys
    if sys.version_info[0] == 3:
        if sys.version_info[1] < 4:
            from imp import reload
        else:
            from importlib import reload
    elif sys.version_info[0] == 2:
        from imp import reload    
    reload(load_lumapi)

  if not lumapi:
    print("SiEPIC.lumerical.interconnect.run_FDTD: lumapi not loaded")
    pya.MessageBox.warning("Cannot load Lumerical Python integration.", "Some SiEPIC-Tools Lumerical functionality will not be available.", pya.MessageBox.Cancel)
    return
    
  if verbose:
    print(_globals.FDTD)  # Python Lumerical FDTD integration handle
  
  if not _globals.FDTD: # Not running, start a new session
    _globals.FDTD = lumapi.open('fdtd')
    if verbose:
      print(_globals.FDTD)  # Python Lumerical FDTD integration handle
  else: # found open FDTD session
    try:
      lumapi.evalScript(_globals.FDTD, "?'KLayout integration test.\n';\n")
    except: # but can't communicate with FDTD; perhaps it was closed by the user
      _globals.FDTD = lumapi.open('fdtd') # run again.
      if verbose:
        print(_globals.FDTD)  # Python Lumerical FDTD integration handle
  try: # check again
    lumapi.evalScript(_globals.FDTD, "?'KLayout integration test.\n';\n")
  except:
    raise Exception ("Can't run Lumerical FDTD via Python integration.")


'''
################################################################################
Lumerical FDTD Solutions simulation for a component
generate S-Parameters

definitions:
  z: thickness direction
  z=0: centre of the waveguides, so we can use symmetric mesh in z
       which will be better for convergence testing as the mesh won't move
################################################################################
'''
def generate_component_sparam(do_simulation = True, addto_CML = True, verbose = False, FDTD_settings = None):
  if verbose:
    print('SiEPIC.lumerical.fdtd: generate_component_sparam()')

  # Get technology and layout details
  from ..utils import get_layout_variables
  TECHNOLOGY, lv, ly, cell = get_layout_variables()  
  dbum = TECHNOLOGY['dbu']*1e-6 # dbu to m conversion

  # get selected instances; only one
  from ..utils import select_instances
  selected_instances = select_instances()
  error = pya.QMessageBox()
  error.setStandardButtons(pya.QMessageBox.Ok )
  if len(selected_instances) != 1:
    error.setText("Error: Need to have one component selected.")
    response = error.exec_()        
    return
  
  # get selected component
  if verbose:
    print(" selected component: %s" % selected_instances[0].inst().cell )
  component = cell.find_components(cell_selected=[selected_instances[0].inst().cell])[0]

  # create an SVG icon for the component, for INTC compact model icon
  from .. import _globals
  import os
  from ..utils import svg_from_component
  svg_filename = os.path.join(_globals.TEMP_FOLDER, '%s.svg' % component.instance)
  if verbose:
    print(" SVG filename: %s" %svg_filename)
  svg_from_component(component, svg_filename)

  # simulation filenames
  fsp_filename = os.path.join(_globals.TEMP_FOLDER, '%s.fsp' % component.instance)
  xml_filename = os.path.join(_globals.TEMP_FOLDER, '%s.xml' % component.instance)
  file_sparam = os.path.join(_globals.TEMP_FOLDER, '%s.dat' % component.instance)

  # get Component pins
  pins = component.find_pins()
  pins = sorted(pins, key=lambda  p: p.pin_name)
  for p in pins:
    p.pin_name = p.pin_name.replace(' ','')  # remove spaces in pin names
  

  if do_simulation:
    import numpy as np
    # run Lumerical FDTD Solutions  
    from .. import _globals
    run_FDTD()
    lumapi = _globals.LUMAPI
    if not lumapi:
      print('SiEPIC.lumerical.fdtd.generate_component_sparam: lumapi not loaded')
      return
      
    if verbose:
      print(lumapi)  # Python Lumerical INTERCONNECT integration handle
  
    # get FDTD settings from XML file
    if not FDTD_settings:
      from SiEPIC.utils import load_FDTD_settings
      FDTD_settings=load_FDTD_settings()
      if FDTD_settings:
        if verbose:
          print(FDTD_settings)
  
    # Configure wavelength and polarization
    # polarization = {'quasi-TE', 'quasi-TM', 'quasi-TE and -TM'}
    mode_selection = FDTD_settings['mode_selection']
    mode_selection_index = []
    if 'fundamental TE mode' in mode_selection or '1' in mode_selection:
      mode_selection_index.append(1)
    if 'fundamental TM mode' in mode_selection or '2' in mode_selection:
      mode_selection_index.append(2)
    if not mode_selection_index:
      error = pya.QMessageBox()
      error.setStandardButtons(pya.QMessageBox.Ok )
      error.setText("Error: Invalid modes requested.")
      response = error.exec_()        
      return

    # wavelength
    wavelength_start = FDTD_settings['wavelength_start']
    wavelength_stop =  FDTD_settings['wavelength_stop']     
  
    # get DevRec layer
    devrec_box = component.DevRec_polygon.bbox()
    print("%s, %s, %s, %s"  % (devrec_box.left*dbum, devrec_box.right*dbum, devrec_box.bottom*dbum, devrec_box.top*dbum) )
  
    # create FDTD simulation region (extra large)
    FDTDzspan=FDTD_settings['Initial_FDTD_Z_span']
    if mode_selection_index==1:
      Z_symmetry = 'Symmetric'
    elif mode_selection_index==2:
      Z_symmetry ='Anti-Symmetric'
    else:
      Z_symmetry = FDTD_settings['Initial_Z-Boundary-Conditions']
    FDTDxmin,FDTDxmax,FDTDymin,FDTDymax = (devrec_box.left)*dbum-200e-9, (devrec_box.right)*dbum+200e-9, (devrec_box.bottom)*dbum-200e-9, (devrec_box.top)*dbum+200e-9
    sim_time = max(devrec_box.width(),devrec_box.height())*dbum * 4.5; 
    lumapi.evalScript(_globals.FDTD, " \
      newproject; \
      addfdtd; set('x min',%s); set('x max',%s); set('y min',%s); set('y max',%s); set('z span',%s);\
      set('force symmetric z mesh', 1); set('mesh accuracy',1); \
      set('x min bc','Metal'); set('x max bc','Metal'); \
      set('y min bc','Metal'); set('y max bc','Metal'); \
      set('z min bc','%s'); set('z max bc','%s'); \
      setglobalsource('wavelength start',%s); setglobalsource('wavelength stop', %s); \
      setglobalmonitor('frequency points',%s); set('simulation time', %s/c+400e-15); \
      addmesh; set('override x mesh',0); set('override y mesh',0); set('override z mesh',1); set('z span', 0); set('dz', %s); set('z', %s); \
      ?'FDTD solver with mesh override added'; " % ( FDTDxmin,FDTDxmax,FDTDymin,FDTDymax,FDTDzspan, \
         Z_symmetry, FDTD_settings['Initial_Z-Boundary-Conditions'], \
         wavelength_start,wavelength_stop, \
         FDTD_settings['frequency_points_monitor'], sim_time, \
         FDTD_settings['thickness_Si']/4, FDTD_settings['thickness_Si']/2) )
  
    # add substrate and cladding:
    lumapi.evalScript(_globals.FDTD, " \
      addrect; set('x min',%s); set('x max',%s); set('y min',%s); set('y max',%s); set('z min', %s); set('z max',%s);\
      set('material', '%s'); set('alpha',0.1);    \
      ?'oxide added';    " % (FDTDxmin-1e-6, FDTDxmax+1e-6, FDTDymin-1e-6, FDTDymax+1e-6, \
        -FDTD_settings['thickness_BOX']-FDTD_settings['thickness_Si']/2, -FDTD_settings['thickness_Si']/2, \
        FDTD_settings['material_Clad'] ) )
    lumapi.evalScript(_globals.FDTD, " \
      addrect; set('x min',%s); set('x max',%s); set('y min',%s); set('y max',%s); set('z min', %s); set('z max',%s);\
      set('material', '%s'); set('alpha',0.1);    \
      ?'oxide added';    " % (FDTDxmin-1e-6, FDTDxmax+1e-6, FDTDymin-1e-6, FDTDymax+1e-6, \
        -FDTD_settings['thickness_Si']/2, FDTD_settings['thickness_Clad']-FDTD_settings['thickness_Si']/2, \
        FDTD_settings['material_Clad'] ) )
  
    # get polygons from component
    polygons = component.get_polygons()
    if verbose:
      print(" polygons: %s" % [p for p in polygons] )
    polygons_vertices = [[[vertex.x*dbum, vertex.y*dbum] for vertex in p.each_point()] for p in [p.to_simple_polygon() for p in polygons] ]
    if verbose:
      print(" polygons' vertices: %s" % len(polygons_vertices) )
    if len(polygons_vertices) < 1:
      error = pya.QMessageBox()
      error.setStandardButtons(pya.QMessageBox.Ok )
      error.setText("Error: Component needs to have polygons.")
      response = error.exec_()        
      return
  
    # send polygons to FDTD
    for i in range(0,len(polygons_vertices)):
      lumapi.putMatrix(_globals.FDTD, "polygon_vertices", np.array(polygons_vertices[i]) )
      lumapi.evalScript(_globals.FDTD, " \
        addpoly; set('vertices',polygon_vertices); \
        set('material', '%s'); set('z span', %s);     \
        ?'Polygons added'; " % (FDTD_settings['material_Si'], FDTD_settings['thickness_Si']) )
      
    # create FDTD ports
    # configure boundary conditions to be PML where we have ports
  #  FDTD_bc = {'y max bc': 'Metal', 'y min bc': 'Metal', 'x max bc': 'Metal', 'x min bc': 'Metal'}
    port_dict = {0.0: 'x max bc', 90.0: 'y max bc', 180.0: 'x min bc', -90.0: 'y min bc'}
    for p in pins:
      if p.rotation in [180.0, 0.0]:
        lumapi.evalScript(_globals.FDTD, " \
          addport; set('injection axis', 'x-axis'); set('x',%s); set('y',%s); set('y span',%s); set('z span',%s); \
          " % (p.center.x*dbum, p.center.y*dbum,2e-6,FDTDzspan)  )
      if p.rotation in [270.0, 90.0, -90.0]:
        lumapi.evalScript(_globals.FDTD, " \
          addport; set('injection axis', 'y-axis'); set('x',%s); set('y',%s); set('x span',%s); set('z span',%s); \
          " % (p.center.x*dbum, p.center.y*dbum,2e-6,FDTDzspan)  )
      if p.rotation in [0.0, 90.0]:
        p.direction = 'Backward'
      else:
        p.direction = 'Forward'
      lumapi.evalScript(_globals.FDTD, " \
        set('name','%s'); set('direction', '%s'); set('frequency points', %s); updateportmodes(%s); \
        select('FDTD'); set('%s','PML'); \
        ?'Added pin: %s, set %s to PML'; " % (p.pin_name, p.direction, 1, mode_selection_index, \
            port_dict[p.rotation], p.pin_name, port_dict[p.rotation] )  )
      
    # Calculate mode sources
    # Get field profiles, to find |E| = 1e-6 points to find spans
    import sys
    if not 'win' in sys.platform:  # Windows getVar ("E") doesn't work.
      min_z, max_z = 0,0
      for p in [pins[0]]:  # if all pins are the same, only do it once
        for m in mode_selection_index:
          lumapi.evalScript(_globals.FDTD, " \
            select('FDTD::ports::%s'); mode_profiles=getresult('FDTD::ports::%s','mode profiles'); E=mode_profiles.E%s; x=mode_profiles.x; y=mode_profiles.y; z=mode_profiles.z; \
            ?'Selected pin: %s'; " % (p.pin_name, p.pin_name, m, p.pin_name)  )
          E=lumapi.getVar(_globals.FDTD, "E")
          x=lumapi.getVar(_globals.FDTD, "x")
          y=lumapi.getVar(_globals.FDTD, "y")
          z=lumapi.getVar(_globals.FDTD, "z")
    
          # remove the wavelength from the array, 
          # leaving two dimensions, and 3 field components
          if p.rotation in [180.0, 0.0]:
            Efield_xyz = np.array(E[0,:,:,0,:])
          else:
            Efield_xyz = np.array(E[:,0,:,0,:])
          # find the field intensity (|Ex|^2 + |Ey|^2 + |Ez|^2)
          Efield_intensity = np.empty([Efield_xyz.shape[0],Efield_xyz.shape[1]])
          print(Efield_xyz.shape)
          for a in range(0,Efield_xyz.shape[0]):
            for b in range(0,Efield_xyz.shape[1]):
              Efield_intensity[a,b] = abs(Efield_xyz[a,b,0])**2+abs(Efield_xyz[a,b,1])**2+abs(Efield_xyz[a,b,2])**2
          # find the max field for each z slice (b is the z axis)
          Efield_intensity_b = np.empty([Efield_xyz.shape[1]])
          for b in range(0,Efield_xyz.shape[1]):
            Efield_intensity_b[b] = max(Efield_intensity[:,b])
          # find the z thickness where the field has sufficiently decayed
          indexes = np.argwhere ( Efield_intensity_b > FDTD_settings['Efield_intensity_cutoff_eigenmode'] )
          min_index, max_index = int(min(indexes)), int(max(indexes))
          if min_z > z[min_index]:
            min_z = z[min_index]
          if max_z < z[max_index]:
            max_z = z[max_index]
          if verbose:
            print(' Port %s, mode %s field decays at: %s, %s microns' % (p.pin_name, m, z[max_index], z[min_index]) )
    
        if FDTDzspan > max_z-min_z:
          FDTDzspan = float(max_z-min_z)
          if verbose:
            print(' Updating FDTD Z-span to: %s microns' % (FDTDzspan) )
     
    # Configure FDTD region, mesh accuracy 1
    # run single simulation
    lumapi.evalScript(_globals.FDTD, " \
      select('FDTD'); set('z span',%s);\
      save('%s');\
      ?'FDTD Z-span updated to %s'; " % (FDTDzspan, fsp_filename, FDTDzspan) )
  
    # Calculate, plot, and get the S-Parameters, S21, S31, S41 ...
    # optionally simulate a subset of the S-Parameters
    # assume input on port 1
    # return Sparams: last mode simulated [wavelength, pin out index], and
    #        Sparams_modes: all modes [mode, wavelength, pin out index]
    def FDTD_run_Sparam_simple(pins, in_pin = None, out_pins = None, modes = [1], plots = False):
      if verbose:
        print(' Run simulation S-Param FDTD')
      Sparams_modes = []
      if not in_pin:
        in_pin = pins[0]
      for m in modes:
        lumapi.evalScript(_globals.FDTD, "\
          switchtolayout; select('FDTD::ports');\
          set('source port','%s');\
          set('source mode','mode %s');\
          run; " % ( in_pin.pin_name, m ) )
        port_pins = [in_pin]+out_pins if out_pins else pins
        for p in port_pins:
          if verbose:
            print(' port %s expansion' % p.pin_name )
          lumapi.evalScript(_globals.FDTD, " \
            P=Port_%s=getresult('FDTD::ports::%s','expansion for port monitor'); \
             " % (p.pin_name,p.pin_name) )
        lumapi.evalScript(_globals.FDTD, "wavelengths=c/P.f*1e6;")
        wavelengths = lumapi.getVar(_globals.FDTD, "wavelengths") 
        Sparams = []
        for p in port_pins[1::]:
          if verbose:
            print(' S_%s_%s Sparam' % (p.pin_name,in_pin.pin_name) )
          lumapi.evalScript(_globals.FDTD, " \
            Sparam=S_%s_%s= Port_%s.%s/Port_%s.%s;  \
             " % (p.pin_name, in_pin.pin_name, \
                  p.pin_name, 'b' if p.direction=='Forward' else 'a', \
                  in_pin.pin_name, 'a' if in_pin.direction=='Forward' else 'b') )
          Sparams.append(lumapi.getVar(_globals.FDTD, "Sparam"))
          if plots:
            if verbose:
              print(' Plot S_%s_%s Sparam' % (p.pin_name,in_pin.pin_name) )
            lumapi.evalScript(_globals.FDTD, " \
              plot (wavelengths, 10*log10(abs(Sparam(:,%s))^2),  'Wavelength (um)', 'Transmission (dB)', 'S_%s_%s, mode %s'); \
               " % (modes.index(m)+1, p.pin_name, in_pin.pin_name, modes.index(m)+1) )
        Sparams_modes.append(Sparams)
      return Sparams, Sparams_modes
    
    # Run the first FDTD simulation
    in_pin = pins[0]
    Sparams, Sparams_modes = FDTD_run_Sparam_simple(pins, in_pin=in_pin, modes = mode_selection_index, plots = True)
  
    # find the pin that has the highest Sparam (max over 1-wavelength and 2-modes)
    # use this Sparam for convergence testing
    # use the highest order mode for the convergence testing and reporting IL values.
    Sparam_pin_max_modes = []
    Mean_IL_best_port = [] # one for each mode
    for m in mode_selection_index:
      Sparam_pin_max_modes.append( np.amax(np.absolute(np.array(Sparams)[:,:,mode_selection_index.index(m)]), axis=1).argmax() + 1 ) 
      Mean_IL_best_port.append( -10*np.log10(np.mean(np.absolute(Sparams)[Sparam_pin_max_modes[-1]-1,:,mode_selection_index.index(m)])**2) ) 
  
    # user verify ok?
    warning = pya.QMessageBox()
    warning.setStandardButtons(pya.QMessageBox.Yes | pya.QMessageBox.Cancel)
    warning.setDefaultButton(pya.QMessageBox.Yes)
    info_text = "First FDTD simulation complete (coarse mesh, lowest accuracy). Highest transmission S-Param: \n"
    for m in mode_selection_index:
      info_text +=  "mode %s, S_%s_%s has %s dB average insertion loss\n" % (m, pins[Sparam_pin_max_modes[mode_selection_index.index(m)]].pin_name, in_pin.pin_name, Mean_IL_best_port[mode_selection_index.index(m)])
    warning.setInformativeText(info_text)
    warning.setText("Do you want to Proceed?")
    if verbose:
      print(info_text)
    else:
      if(pya.QMessageBox_StandardButton(warning.exec_()) == pya.QMessageBox.Cancel):
        return
  
    # Convergence testing on S-Parameters:
    # convergence test on simulation z-span (assume symmetric increases)
    # loop in Python so we can check if it is good enough
    # use the highest order mode
    mode_convergence = [mode_selection_index[-1]]
    Sparam_pin_max = Sparam_pin_max_modes[-1]
    if FDTD_settings['convergence_tests']:
      test_converged = False
      convergence = []
      Sparams_abs_prev = np.array([np.absolute(Sparams)[Sparam_pin_max-1,:,:]])
      while not test_converged:
        FDTDzspan += FDTD_settings['convergence_test_span_incremement']
        lumapi.evalScript(_globals.FDTD, " \
          switchtolayout; select('FDTD'); set('z span',%s);\
          " % (FDTDzspan) )
        Sparams, Sparams_modes = FDTD_run_Sparam_simple(pins, in_pin=in_pin, out_pins = [pins[Sparam_pin_max]], modes = mode_convergence, plots = True)
        Sparams_abs = np.array(np.absolute(Sparams))
        rms_error = np.sqrt(np.mean( (Sparams_abs_prev - Sparams_abs)**2 ))
        convergence.append ( [FDTDzspan, rms_error] )
        Sparams_abs_prev = Sparams_abs
        if verbose:
          print (' convergence: span and rms error %s' % convergence[-1] ) 
        lumapi.evalScript(_globals.FDTD, " \
          ?'FDTD Z-span: %s, rms error from previous: %s (convergence testing until < %s)'; " % (FDTDzspan, rms_error, FDTD_settings['convergence_test_rms_error_limit']) )
        if rms_error < FDTD_settings['convergence_test_rms_error_limit']:
          test_converged=True
          FDTDzspan += -1*FDTD_settings['convergence_test_span_incremement']
        # check if the last 3 points have reducing rms
        if len(convergence) > 2:
          test_rms = np.polyfit(np.array(convergence)[-3:,0], np.array(convergence)[-3:,1], 1)
          if verbose:
            print ('  convergence rms trend: %s; fit data: %s' %  (test_rms, np.array(convergence)[:,-3:]) )
          if test_rms[0] > 0:
            if verbose:
              print (' convergence problem, not improving rms. terminating convergence test.'  ) 
            lumapi.evalScript(_globals.FDTD, "?'convergence problem, not improving rms. terminating convergence test.'; "  )
            test_converged=True
            FDTDzspan += -2*FDTD_settings['convergence_test_span_incremement']
    
      lumapi.putMatrix(_globals.FDTD, 'convergence', convergence)
      lumapi.evalScript(_globals.FDTD, "plot(convergence(:,1), convergence(:,2), 'Simulation span','RMS error between simulation','Convergence testing');")
  
    # Perform quick corner analysis
    if FDTD_settings['Perform-quick-corner-analysis']:
      pass
  
    # Configure FDTD region, higher mesh accuracy, update FDTD ports mode source frequency points
    lumapi.evalScript(_globals.FDTD, " \
      switchtolayout; select('FDTD'); set('mesh accuracy',%s);\
      set('z min bc','%s'); set('z max bc','%s'); \
      ?'FDTD mesh accuracy updated %s, Z boundary conditions: %s'; " % (FDTD_settings['mesh_accuracy'], FDTD_settings['Z-Boundary-Conditions'], FDTD_settings['Z-Boundary-Conditions'], FDTD_settings['mesh_accuracy'], FDTD_settings['Z-Boundary-Conditions']) )
    for p in pins:
      lumapi.evalScript(_globals.FDTD, " \
        select('FDTD::ports::%s'); set('frequency points', %s); \
        ?'updated pin: %s'; " % (p.pin_name, FDTD_settings['frequency_points_expansion'], p.pin_name)  )
    
    # Run full S-parameters
    # add s-parameter sweep task
    lumapi.evalScript(_globals.FDTD, " \
      deletesweep('s-parameter sweep'); \
      addsweep(3); \
      NPorts=%s; \
      " % (len(pins))  )
    for p in pins:
      for m in mode_selection_index:
        # add index entries to s-matrix mapping table
        lumapi.evalScript(_globals.FDTD, " \
          index1 = struct; \
          index1.Port = '%s'; \
          index1.Mode = 'mode %s'; \
          addsweepparameter('s-parameter sweep',index1); \
        " % (p.pin_name, m))
    
    # run s-parameter sweep, collect results, visualize results
    # export S-parameter data to file named xxx.dat to be loaded in INTERCONNECT
    lumapi.evalScript(_globals.FDTD, " \
      runsweep('s-parameter sweep'); \
      S_matrix = getsweepresult('s-parameter sweep','S matrix'); \
      S_parameters = getsweepresult('s-parameter sweep','S parameters'); \
      S_diagnostic = getsweepresult('s-parameter sweep','S diagnostic'); \
      visualize(S_parameters); \
      exportsweep('s-parameter sweep','%s'); \
      " % (file_sparam) )
    if verbose:
      print(" S-Parameter file: %s" % file_sparam)
  
    # Perform final corner analysis, for Monte Carlo simulations
    if FDTD_settings['Perform-final-corner-analysis']:
      pass
  
  
    # Write XML file for INTC scripted compact model
    # height and width are set to the first pin width/height
    xml_out = '\
      <?xml version="1.0" encoding="UTF-8"?> \n\
      <lumerical_lookup_table version="1.0" name = "index_table"> \n\
      <association> \n\
          <design> \n\
              <value name="height" type="double">%s</value> \n\
              <value name="width" type="double">%s</value> \n\
          </design> \n\
          <extracted> \n\
              <value name="sparam" type="string">%s</value> \n\
          </extracted> \n\
      </association>\n' % (FDTD_settings['thickness_Si'], pins[0].path.width*dbum, component.instance)
    fh = open(xml_filename, "w")
    fh.writelines(xml_out)
    fh.close()

    if verbose:
      print(" XML file: %s" % xml_filename)


  if addto_CML:
    # Run using Python integration:
    from . import interconnect
    interconnect.run_INTC()
    from .. import _globals
    lumapi = _globals.LUMAPI
  
    # Copy files to the INTC Custom library folder
    lumapi.evalScript(_globals.INTC, "out=customlibrary;")
    INTC_custom=lumapi.getVar(_globals.INTC, "out")
    
      
    # Create a component
    port_dict2 = {0.0: 'Right', 90.0: 'Top', 180.0: 'Left', -90.0: 'Bottom'}
    t = 'switchtodesign; deleteall; \n'
    t+= 'addelement("Optical N Port S-Parameter"); createcompound; select("COMPOUND_1");\n'
    t+= 'component = "%s"; set("name",component); \n' % component.instance
    import os
    if os.path.exists(svg_filename):
      t+= 'seticon(component,"%s");\n' %(svg_filename)
    else:
      print(" SiEPIC.lumerical.fdtd.component... missing SVG icon: %s" % svg_filename)
    t+= 'select(component+"::SPAR_1"); set("load from file", true);\n'
    t+= 'set("s parameters filename", "%s");\n' % (file_sparam)
    t+= 'set("load from file", false);\n'
    t+= 'set("passivity", "enforce");\n'
    t+= 'set("prefix", component);\n'
    t+= 'setposition(component+"::SPAR_1",100,-100);\n'
    count=0
    for p in pins:
      count += 1
      if p.rotation in [0.0, 180.0]:
        location = 1-(p.center.y-component.DevRec_polygon.bbox().bottom+0.)/component.DevRec_polygon.bbox().height()
  #      print(" p.y %s, c.bottom %s, location %s: " % (p.center.y,component.polygon.bbox().bottom, location) )
      else:
        location = (p.center.x-component.DevRec_polygon.bbox().left+0.)/component.DevRec_polygon.bbox().width()
        print(location)
      t+= 'addport(component, "%s", "Bidirectional", "Optical Signal", "%s",%s);\n' %(p.pin_name,port_dict2[p.rotation],location)
      t+= 'connect(component+"::RELAY_%s", "port", component+"::SPAR_1", "port %s");\n' % (count, count)
    t+= 'select(component); addtolibrary("SiEPIC_user",true);\n'
    t+= '?"created and added " + component + " to library SiEPIC_user";\n'
    lumapi.evalScript(_globals.INTC, t)  
  
  
    # Script for the component, to load S-Param data:
    t= '###############################################\n'
    t+='# SiEPIC ebeam compact model library (CML)\n'
    t+='# custom generated component created by SiEPIC-Tools; script by Zeqin Lu, Xu Wang, Lukas Chrostowski\n'
    t+='?filename = %local path%+"/source_data/' + '%s/%s.xml";\n' % (component.instance,component.instance)
    
    
    
    # Monte Carlo part:
    '''
    if (MC_non_uniform==1) {
    
        x=%x coordinate%;
        y=%y coordinate%;
    
        x1_wafer = floor(x/MC_grid); # location of component on the wafer map
        y1_wafer = floor(y/MC_grid);
    
        devi_width = MC_uniformity_width(MC_resolution_x/2 + x1_wafer, MC_resolution_y/2 + y1_wafer)*1e-9;
        devi_thickness = MC_uniformity_thickness(MC_resolution_x/2 + x1_wafer, MC_resolution_y/2 + y1_wafer)*1e-9;                     
    
        initial_width = 500e-9;
        initial_thickness = 220e-9;
    
        waveguide_width = initial_width + devi_width;  # [m]
        waveguide_thickness = initial_thickness + devi_thickness; # [m]
    
    
        # effective index and group index interpolations
        # The following built-in script interpolates effective index (neff), group index (ng), and dispersion, 
        # and applies the interpolated results to the waveguide. 
    
        filename = %local path%+"/source_data/y_branch_source/y_lookup_table.xml";
        table = "index_table";
    
        design = cell(2);
        extracted = cell(1);
    
        #design (input parameters)
        design{1} = struct;
        design{1}.name = "width";
        design{1}.value = waveguide_width;
        design{2} = struct;
        design{2}.name = "height";  
        design{2}.value = waveguide_thickness; 
    
       M = lookupreadnportsparameter(filename, table, design, "y_sparam");
    
       setvalue('SPAR_1','s parameters',M);
    
    }
    else {
        filename = %local path%+"/source_data/y_branch_source/y_lookup_table.xml";
        table = "index_table";
    
        design = cell(2);
        extracted = cell(1);
    
        #design (input parameters)
        design{1} = struct;
        design{1}.name = "width";
        design{1}.value = 500e-9;
        design{2} = struct;
        design{2}.name = "height";  
        design{2}.value = 220e-9; 
    
       M = lookupreadnportsparameter(filename, table, design, "y_sparam");
    
       setvalue('SPAR_1','s parameters',M);
        
    }
    
    '''

  return component.instance, file_sparam, [], xml_filename, svg_filename




