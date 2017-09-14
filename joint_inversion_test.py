
import time

import numpy as np
import matplotlib.pyplot as plt
import copy 

from pysit import *
from pysit.gallery import horizontal_reflector
from pysit_extensions.joint_objective_di.joint_model import *
from pysit.gallery import marmousi


def model_reg_objective(joint_model, beta, model_reg_term_scale):
    model_diff = joint_model.m_0 - joint_model.m_1
    take_norm_squared_of_this = model_diff*(1/beta)
    take_norm_squared_of_this = joint_model.m_0.perturbation(data=take_norm_squared_of_this)
    objective_value_contrib_from_beta = 0.5*model_reg_term_scale*take_norm_squared_of_this.inner_product(take_norm_squared_of_this) 

    return objective_value_contrib_from_beta

def model_reg_gradient(joint_model, beta, model_reg_term_scale):
    model_diff = joint_model.m_0 - joint_model.m_1     gradient_m_0_contrib_from_beta = model_diff*(model_reg_term_scale*(1/beta)**2)
    gradient_m_0_contrib_from_beta = joint_model.m_0.perturbation(data=gradient_m_0_contrib_from_beta)
        
    gradient_m_1_contrib_from_beta = model_diff*(-model_reg_term_scale*(1/beta)**2)
    gradient_m_1_contrib_from_beta = joint_model.m_1.perturbation(data=gradient_m_1_contrib_from_beta)
                
    joint_model_reg_gradient = JointPerturbation(gradient_m_0_contrib_from_beta, gradient_m_1_contrib_from_beta)    

    return joint_model_reg_gradient

def data_obj_and_gradient(solver,objective, joint_model, shots_0, shots_1):
    aux_info = {'objective_value': (True, None),
                'residual_norm': (True, None)
                }
    
    solver.model_parameters = joint_model.m_0
    gradient_m_0 = objective.compute_gradient(shots_0, joint_model.m_0, aux_info=aux_info)
    objective_value_m_0 = aux_info['objective_value'][1]
    
    aux_info_copy = copy.deepcopy(aux_info)

    #

    solver.model_parameters = joint_model.m_1
    gradient_m_1 = objective.compute_gradient(shots_1, joint_model.m_1, aux_info=aux_info_copy)
    objective_value_m_1 = aux_info_copy['objective_value'][1]    
        
    joint_data_obj = objective_value_m_0 + objective_value_m_1
    joint_data_gradient = JointPerturbation(gradient_m_0, gradient_m_1)

    return joint_data_obj, joint_data_gradient

if __name__ == '__main__':
    pixel_scale = [50.0, 50.0]
    
    C, C0, m, d = marmousi(patch='mini_square', pixel_scale=pixel_scale)


    # Set up shots
    shots = equispaced_acquisition(m,
                                   RickerWavelet(4.0),
                                   sources=3,
                                   source_depth=200.0,
                                   source_kwargs={},
                                   receivers='max',
                                   receiver_kwargs={},
                                   )

    # Define and configure the wave solver
    trange = (0.0, 3.0)

    solver = ConstantDensityAcousticWave(m,
                                         spatial_accuracy_order=6,
                                         trange=trange,
                                         kernel_implementation='cpp')

    # Generate synthetic Seismic data
    tt = time.time()
    wavefields =  []
    
    base_model = solver.ModelParameters(m,{'C': C})
    
    model_baseline = solver.ModelParameters(m,{'C': C    })
  
    model_monitor = model_baseline + model_baseline.perturbation(data=1.0e-9*np.ones(model_baseline.C.shape))
    wrong_init_model_test = 0.5*(model_baseline + model_monitor)
    
    

    joint_model = JointModel(model_baseline, model_monitor)
  

                                                    
    
    shots_baseline = shots
    shots_monitor  = copy.deepcopy(shots_baseline)
    
    generate_seismic_data(shots_baseline, solver, model_baseline, wavefields=wavefields)
    generate_seismic_data(shots_monitor, solver, model_monitor, wavefields=wavefields)

    print 'Data generation: {0}s'.format(time.time()-tt)

    objective = TemporalLeastSquares(solver)

    # Define the inversion algorithm
    invalg_joint = LBFGS(objective, memory_length = 5)
    initial_value = solver.ModelParameters(m,{'C': C0})

    # Execute inversion algorithm
    print('Running LBFGS...')
    tt = time.time()

    nsteps = 8

    status_configuration = {'value_frequency'           : 1,
                            'residual_frequency'        : 1,
                            'residual_length_frequency' : 1,
                            'objective_frequency'       : 1,
                            'step_frequency'            : 1,
                            'step_length_frequency'     : 1,
                            'gradient_frequency'        : 1,
                            'gradient_length_frequency' : 1,
                            'run_time_frequency'        : 1,
                            'alpha_frequency'           : 1,
                            }


    line_search = 'backtrack'

    n_nodes_x = m.x.n
    n_nodes_z = m.z.n

    beta_normalize_2d                  = 1e-2 * np.ones((n_nodes_z, n_nodes_x))
    

    for x_node in xrange(n_nodes_x/2, n_nodes_x):
        beta_normalize_2d[:, x_node] = np.linspace(0.8,1.0, n_nodes_z)
    

    
    beta_normalize = np.reshape(beta_normalize_2d, (n_nodes_z*n_nodes_x,1),'F')


    
    alpha = 1e-9
    joint_model_reg_grad = model_reg_gradient(joint_model, beta_normalize, model_reg_term_scale)
    dm = -alpha*joint_model_reg_grad*(1.0/joint_model_reg_grad.norm()) grow when the gradient changes length through model_reg_term_scale
    change_in_grad_direction = joint_model_reg_grad.inner_product(dm)
    
    val_alpha = model_reg_objective(joint_model+dm, beta_normalize, model_reg_term_scale)
    val       = model_reg_objective(joint_model   , beta_normalize, model_reg_term_scale)
    discrete_approx = (val_alpha - val)
    

    
    #
    joint_model_init_test = JointModel(wrong_init_model_test, copy.deepcopy(wrong_init_model_test))
    
    [joint_data_obj, joint_data_grad] = data_obj_and_gradient(solver,objective, joint_model_init_test, shots_baseline, shots_monitor)
    
    alpha = 1e-9
    dm = -alpha*joint_data_grad 
    change_in_grad_direction_data = joint_data_grad.inner_product(dm)
    
    [joint_data_obj_alpha, joint_data_grad_will_not_use] = data_obj_and_gradient(solver,objective, joint_model_init_test+dm, shots_baseline, shots_monitor)
    
    discrete_approx_data = (joint_data_obj_alpha - joint_data_obj) 
    





