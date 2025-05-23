# %%  # noqa: INP001, D100
import pyvista as pv  # noqa: I001
import numpy as np
import ctypes
import os
import sys
import h5py
from scipy.spatial import KDTree


def partition_with_pilebox(messh, numcores, pileboxinfo, tol=1e-6):  # noqa: C901, D103
    if pileboxinfo['Havepilebox'] == False:  # noqa: E712
        print('No pilebox is defined')  # noqa: T201
        partition(messh, numcores)
        return

    # separate the core of the pilebox
    mesh = messh.copy()
    eps = 1e-6
    # check if the xmin,xmax, ymin ymax ,zmin zmax is exist in the infokeys
    if 'xmin' in pileboxinfo.keys():  # noqa: SIM118
        pilebox_xmin = pileboxinfo['xmin']
    if 'xmax' in pileboxinfo.keys():  # noqa: SIM118
        pilebox_xmax = pileboxinfo['xmax']
    if 'ymin' in pileboxinfo.keys():  # noqa: SIM118
        pilebox_ymin = pileboxinfo['ymin']
    if 'ymax' in pileboxinfo.keys():  # noqa: SIM118
        pilebox_ymax = pileboxinfo['ymax']
    if 'zmin' in pileboxinfo.keys():  # noqa: SIM118
        pilebox_zmin = pileboxinfo['zmin']
    if 'zmax' in pileboxinfo.keys():  # noqa: SIM118
        pilebox_zmax = pileboxinfo['zmax']
    if 'center' in pileboxinfo.keys():  # noqa: SIM118
        pilebox_xmin = pileboxinfo['center'][0] - pileboxinfo['lx'] / 2 + eps
        pilebox_xmax = pileboxinfo['center'][0] + pileboxinfo['lx'] / 2 - eps
        pilebox_ymin = pileboxinfo['center'][1] - pileboxinfo['ly'] / 2 + eps
        pilebox_ymax = pileboxinfo['center'][1] + pileboxinfo['ly'] / 2 - eps
        pilebox_zmin = pileboxinfo['center'][2] - pileboxinfo['depth'] + eps
        pilebox_zmax = pileboxinfo['center'][2] + tol + eps

    # find the cells that are inside the pilebox
    cube = pv.Cube(
        bounds=[
            pilebox_xmin,
            pilebox_xmax,
            pilebox_ymin,
            pilebox_ymax,
            pilebox_zmin,
            pilebox_zmax,
        ]
    )
    # extract the cells that are outside the pilebox
    indices = mesh.find_cells_within_bounds(cube.bounds)

    # crete newindices for outside the pilebox
    newindices = np.ones(mesh.n_cells, dtype=bool)
    newindices[indices] = False
    newindices = np.where(newindices)[0]

    # extract the cells that are inside the pilebox
    mesh2 = mesh.extract_cells(newindices)
    # partition the mesh

    if numcores > 2:  # noqa: PLR2004
        partition(mesh2, numcores - 1)
    if numcores == 2:  # noqa: PLR2004
        mesh2.cell_data['partitioned'] = np.zeros(mesh2.n_cells, dtype=np.int32)

    mesh.cell_data['partitioned'] = np.zeros(mesh.n_cells, dtype=np.int32)
    mesh.cell_data['partitioned'][newindices] = mesh2.cell_data['partitioned'] + 1
    messh.cell_data['partitioned'] = mesh.cell_data['partitioned']


def partition(mesh, numcores):  # noqa: D103
    # =============================================================================
    # define partioner
    # =============================================================================

    libpath = (
        os.getcwd().split('OpenSeesProjects')[0]  # noqa: PTH109
        + 'OpenSeesProjects/'
        + 'MeshGenerator/lib'
    )
    if os.name == 'nt':
        metis_partition_lib = ctypes.CDLL(f'{libpath}/Partitioner.dll')
    if os.name == 'posix':
        metis_partition_lib = ctypes.CDLL(f'{libpath}/libPartitioner.so')

    # Define function argument and return types
    metis_partition_lib.Partition.argtypes = [
        ctypes.c_int,
        ctypes.c_int,
        ctypes.POINTER(ctypes.c_int32),
        ctypes.c_int,
        ctypes.POINTER(ctypes.c_int32),
    ]
    metis_partition_lib.Partition.restype = ctypes.c_int

    numcells = mesh.n_cells
    numpoints = mesh.n_points
    numweights = 1  # noqa: F841
    cells = np.array(mesh.cells.reshape(-1, 9), dtype=np.int32)
    cells = cells[:, 1:]
    cellspointer = cells.flatten().ctypes.data_as(ctypes.POINTER(ctypes.c_int32))
    partitioned = np.empty(numcells, dtype=np.int32)
    partitionedpointer = partitioned.ctypes.data_as(ctypes.POINTER(ctypes.c_int32))
    metis_partition_lib.Partition(
        numcells, numpoints, cellspointer, numcores, partitionedpointer
    )
    mesh.cell_data['partitioned'] = partitioned


def kdtree_partition(grid, n_partitions=4):  # noqa: D103
    blocks = grid.partition(n_partitions, generate_global_id=True, as_composite=True)
    i = 0
    grid['partitioned'] = np.zeros(grid.n_cells, dtype=np.int32)
    for block in blocks:
        grid['partitioned'][block['vtkGlobalCellIds']] = i
        i += 1  # noqa: SIM113


def DRM_PML_Foundation_Meshgenrator(meshinfo):  # noqa: C901, N802, D103, PLR0912, PLR0915
    xwidth, ywidth, zwidth = (
        meshinfo['xwidth'],
        meshinfo['ywidth'],
        meshinfo['zwidth'],
    )
    eps = 1e-6
    Xmeshsize, Ymeshsize, Zmeshsize = (  # noqa: N806
        meshinfo['Xmeshsize'],
        meshinfo['Ymeshsize'],
        meshinfo['Zmeshsize'],
    )
    PMLThickness = np.array(  # noqa: N806
        [
            meshinfo['PMLThickness'][0],
            meshinfo['PMLThickness'][1],
            meshinfo['PMLThickness'][2],
        ]
    )  # thickness of the each PML layer
    numPMLLayers = meshinfo['numPMLLayers']  # number of PML layers  # noqa: N806
    PMLTotalThickness = (  # noqa: N806
        PMLThickness * numPMLLayers
    )  # total thickness of the PML layers
    DRMThickness = np.array(  # noqa: N806
        [
            meshinfo['DRMThickness'][0],
            meshinfo['DRMThickness'][1],
            meshinfo['DRMThickness'][2],
        ]
    )  # thickness of the DRM layers
    numDrmLayers = meshinfo['numDrmLayers']  # number of DRM layers  # noqa: N806
    DRMTotalThickness = (  # noqa: N806
        DRMThickness * numDrmLayers
    )  # total thickness of the DRM layers
    padLayers = (  # noqa: F841, N806
        numPMLLayers + numDrmLayers
    )  # number of layers to pad the meshgrid
    padThickness = (  # noqa: N806, F841
        PMLTotalThickness + DRMThickness
    )  # thickness of the padding layers
    reg_num_cores = meshinfo['reg_num_cores']
    DRM_num_cores = meshinfo['DRM_num_cores']  # noqa: N806
    PML_num_cores = meshinfo['PML_num_cores']  # noqa: N806
    structurecores = meshinfo['Structure_num_cores']
    Dir = meshinfo['Dir']  # noqa: N806
    OutputDir = meshinfo['OutputDir']  # noqa: N806
    AbsorbingElements = meshinfo['AbsorbingElements']  # noqa: N806
    DRMfile = meshinfo['DRMfile']  # noqa: N806
    foundationBlocks = meshinfo['foundationBlocks']  # noqa: N806
    pilelist = meshinfo['pilelist']
    EmbeddeFoundation = meshinfo['EmbeddedFoundationDict']  # noqa: N806
    HaveEmbeddingFoundation = meshinfo['EmbeddingFoundation']  # noqa: N806
    HaveFoundation = meshinfo['HaveFoundation']  # noqa: N806
    HavePiles = meshinfo['HavePiles']  # noqa: N806
    HaveStructure = meshinfo['HaveStructure']  # noqa: N806
    AttachFoundation = meshinfo['AttachFoundation']  # noqa: N806
    DRMinformation = meshinfo['DRMinformation']  # noqa: N806
    PartitionAlgorithm = meshinfo['PartitionAlgorithm']  # noqa: N806

    # =============================================================================
    if HaveStructure != 'YES':
        structurecores = 0

    # create a dictionary for meshing information
    info = {
        'Foundation': 1,
        'RegularDomain': 2,
        'DRMDomain': 3,
        'PMLDomain': 4,
    }
    DomainNames = ['Foundation', 'Soil', 'Soil', 'PML']  # noqa: N806

    pileboxinfo = {}

    if not os.path.exists(Dir):  # noqa: PTH110
        os.makedirs(Dir)  # noqa: PTH103
    else:
        # remove the files in the directory
        for file in os.listdir(Dir):
            try:
                os.remove(os.path.join(Dir, file))  # noqa: PTH107, PTH118
            except:  # noqa: S112, PERF203, E722
                continue

    # adding different plots
    meshplotdir = Dir + '/../meshplots'
    if not os.path.exists(meshplotdir):  # noqa: PTH110
        os.makedirs(meshplotdir)  # noqa: PTH103

    # =============================================================================
    # meshing
    # =============================================================================
    x = np.arange(-xwidth / 2.0, xwidth / 2.0 + eps, Xmeshsize)
    y = np.arange(-ywidth / 2.0, ywidth / 2.0 + eps, Ymeshsize)
    z = np.arange(-zwidth, 0 + eps, Zmeshsize)

    # padding x and y for PML and DRM layers
    x = np.pad(
        x,
        (numDrmLayers, numDrmLayers),
        'linear_ramp',
        end_values=(x.min() - DRMTotalThickness[0], x.max() + DRMTotalThickness[0]),
    )
    y = np.pad(
        y,
        (numDrmLayers, numDrmLayers),
        'linear_ramp',
        end_values=(y.min() - DRMTotalThickness[1], y.max() + DRMTotalThickness[1]),
    )
    z = np.pad(
        z,
        (numDrmLayers, 0),
        'linear_ramp',
        end_values=(z.min() - DRMTotalThickness[2]),
    )

    # padding the x and y for PML and PML layers
    x = np.pad(
        x,
        (numPMLLayers, numPMLLayers),
        'linear_ramp',
        end_values=(x.min() - PMLTotalThickness[0], x.max() + PMLTotalThickness[0]),
    )
    y = np.pad(
        y,
        (numPMLLayers, numPMLLayers),
        'linear_ramp',
        end_values=(y.min() - PMLTotalThickness[1], y.max() + PMLTotalThickness[1]),
    )
    z = np.pad(
        z,
        (numPMLLayers, 0),
        'linear_ramp',
        end_values=(z.min() - PMLTotalThickness[2]),
    )

    x, y, z = np.meshgrid(x, y, z, indexing='ij')

    mesh = pv.StructuredGrid(x, y, z)
    mesh.cell_data['Domain'] = (
        np.ones(mesh.n_cells, dtype=np.int8) * info['RegularDomain']
    )
    # =============================================================================
    # separate embedding layer
    # =============================================================================
    if HaveEmbeddingFoundation == 'YES':
        cube = pv.Cube(
            bounds=[
                EmbeddeFoundation['xmin'],
                EmbeddeFoundation['xmax'],
                EmbeddeFoundation['ymin'],
                EmbeddeFoundation['ymax'],
                EmbeddeFoundation['zmin'],
                EmbeddeFoundation['zmax'],
            ]
        )
        mesh = mesh.clip_box(cube, invert=True, crinkle=True, progress_bar=False)
        mesh.clear_data()
        mesh.cell_data['Domain'] = (
            np.ones(mesh.n_cells, dtype=np.int8) * info['RegularDomain']
        )
    # =============================================================================
    # Add foundation blocks
    # =============================================================================
    if HaveFoundation == 'YES':
        for i, block in enumerate(foundationBlocks):
            xBLOCK = np.arange(  # noqa: N806
                block['xmin'], block['xmax'] + eps, block['Xmeshsize']
            )
            yBLOCK = np.arange(  # noqa: N806
                block['ymin'], block['ymax'] + eps, block['Ymeshsize']
            )
            zBLOCK = np.arange(  # noqa: N806
                block['zmin'], block['zmax'] + eps, block['Zmeshsize']
            )
            xBLOCK, yBLOCK, zBLOCK = np.meshgrid(  # noqa: N806
                xBLOCK, yBLOCK, zBLOCK, indexing='ij'
            )
            if i == 0:
                foundation = pv.StructuredGrid(xBLOCK, yBLOCK, zBLOCK)
            else:
                foundation = foundation.merge(
                    pv.StructuredGrid(xBLOCK, yBLOCK, zBLOCK),
                    merge_points=False,
                    tolerance=1e-6,
                    progress_bar=False,
                )

    # =============================================================================
    # adding piles
    # =============================================================================
    pilenodes = np.zeros((len(pilelist) * 2, 3))
    pileelement = np.zeros((len(pilelist), 3), dtype=int)
    for i in range(len(pilelist)):
        pilenodes[i * 2] = [
            pilelist[i]['xtop'],
            pilelist[i]['ytop'],
            pilelist[i]['ztop'],
        ]
        pilenodes[i * 2 + 1] = [
            pilelist[i]['xbottom'],
            pilelist[i]['ybottom'],
            pilelist[i]['zbottom'],
        ]
        pileelement[i] = [2, 2 * i, 2 * i + 1]
    celltypes = np.ones(pileelement.shape[0], dtype=int) * pv.CellType.LINE
    piles = pv.UnstructuredGrid(
        pileelement.tolist(), celltypes.tolist(), pilenodes.tolist()
    )

    pl = pv.Plotter()
    if HavePiles == 'YES':
        pl.add_mesh(
            piles,
            show_edges=True,
            color='r',
            line_width=4.0,
        )
    if HaveFoundation == 'YES':
        pl.add_mesh(foundation, show_edges=True, color='gray', opacity=0.5)
    pl.add_mesh(mesh, opacity=0.5)
    pl.camera_position = 'xz'
    pl.export_html(meshplotdir + '/pile.html')
    # pl.show()

    # merge the piles and foundation
    if HaveFoundation == 'YES' and HavePiles == 'YES':
        foundation2 = foundation.merge(
            piles, merge_points=False, tolerance=1e-6, progress_bar=False
        )
        foundationbounds = foundation2.bounds
        pileboxinfo['xmin'] = foundationbounds[0]
        pileboxinfo['xmax'] = foundationbounds[1]
        pileboxinfo['ymin'] = foundationbounds[2]
        pileboxinfo['ymax'] = foundationbounds[3]
        pileboxinfo['zmin'] = foundationbounds[4]
        pileboxinfo['zmax'] = foundationbounds[5]
        pileboxinfo['Havepilebox'] = True
        del foundation2
    else:
        pileboxinfo['Havepilebox'] = False
    if HaveFoundation == 'YES':
        foundation.cell_data['Domain'] = (
            np.ones(foundation.n_cells, dtype=np.int8) * info['Foundation']
        )
        if AttachFoundation == 'YES':
            mesh = mesh.merge(
                foundation, merge_points=True, tolerance=1e-6, progress_bar=False
            )
        else:
            mesh = mesh.merge(
                foundation, merge_points=False, tolerance=1e-6, progress_bar=False
            )

    # delete  foundation2
    # print("Havepilebox:",pileboxinfo["Havepilebox"])

    # =============================================================================
    # separate PML layer
    # =============================================================================
    xmin = x.min() + PMLTotalThickness[0]
    xmax = x.max() - PMLTotalThickness[0]
    ymin = y.min() + PMLTotalThickness[1]
    ymax = y.max() - PMLTotalThickness[1]
    zmin = z.min() + PMLTotalThickness[2]
    zmax = z.max() + PMLTotalThickness[2]
    cube = pv.Cube(bounds=[xmin, xmax, ymin, ymax, zmin, 1000.0])
    PML = mesh.clip_box(cube, invert=True, crinkle=True, progress_bar=False)  # noqa: N806
    reg = mesh.clip_box(cube, invert=False, crinkle=True, progress_bar=False)

    # now find DRM layer
    indices = reg.find_cells_within_bounds(
        [
            xmin + DRMTotalThickness[0] + eps,
            xmax - DRMTotalThickness[0] - eps,
            ymin + DRMTotalThickness[1] + eps,
            ymax - DRMTotalThickness[1] - eps,
            zmin + DRMTotalThickness[2] + eps,
            zmax + DRMTotalThickness[2] + eps,
        ]
    )

    # now create complemntary indices for DRM
    DRMindices = np.ones(reg.n_cells, dtype=bool)  # noqa: N806
    DRMindices[indices] = False
    DRMindices = np.where(DRMindices)[0]  # noqa: N806

    # reg.cell_data['Domain'] = np.ones(reg.n_cells,dtype=np.int8)*info["DRMDomain"]
    # reg.cell_data['Domain'][indices] = info["RegularDomain"]

    reg.cell_data['Domain'][DRMindices] = info['DRMDomain']
    PML.cell_data['Domain'] = np.ones(PML.n_cells, dtype=np.int8) * info['PMLDomain']
    reg.cell_data['partitioned'] = np.zeros(reg.n_cells, dtype=np.int32)
    PML.cell_data['partitioned'] = np.zeros(PML.n_cells, dtype=np.int32)

    # partitioning regular mesh
    regular = reg.extract_cells(indices, progress_bar=False)
    DRM = reg.extract_cells(DRMindices, progress_bar=False)  # noqa: N806
    regularvtkOriginalCellIds = regular['vtkOriginalCellIds']  # noqa: N806
    DRMvtkOriginalCellIds = DRM['vtkOriginalCellIds']  # noqa: N806

    if reg_num_cores > 1:
        if PartitionAlgorithm.lower() == 'metis':
            print('Using Metis partitioning')  # noqa: T201
            partition_with_pilebox(regular, reg_num_cores, pileboxinfo, tol=10)
        if PartitionAlgorithm.lower() == 'kd-tree':
            print('Using KD-Tree partitioning')  # noqa: T201
            kdtree_partition(regular, reg_num_cores)

    if DRM_num_cores > 1:
        if PartitionAlgorithm.lower() == 'metis':
            partition(DRM, DRM_num_cores)
        if PartitionAlgorithm.lower() == 'kd-tree':
            kdtree_partition(DRM, DRM_num_cores)

    if PML_num_cores > 1:
        if PartitionAlgorithm.lower() == 'metis':
            partition(PML, PML_num_cores)
        if PartitionAlgorithm.lower() == 'kd-tree':
            PMLcopy = PML.copy()  # noqa: N806
            kdtree_partition(PMLcopy, PML_num_cores)
            PML.cell_data['partitioned'] = PMLcopy['partitioned']
            del PMLcopy

    reg.cell_data['partitioned'][regularvtkOriginalCellIds] = regular.cell_data[
        'partitioned'
    ]
    reg.cell_data['partitioned'][DRMvtkOriginalCellIds] = (
        DRM.cell_data['partitioned'] + reg_num_cores
    )
    PML.cell_data['partitioned'] = (
        PML.cell_data['partitioned'] + reg_num_cores + DRM_num_cores
    )

    # regular.plot(scalars="partitioned",show_edges=True)
    # DRM.plot(scalars="partitioned",show_edges=True)
    # PML.plot(scalars="partitioned",show_edges=True)

    # merging PML and regular mesh to create a single mesh
    mesh = reg.merge(PML, merge_points=False, tolerance=1e-6, progress_bar=False)
    # stack the regular and DRM partitioned data
    # mesh.plot(scalars="partitioned",show_edges=True)

    # mapping between PML and regular mesh on the boundary
    mapping = mesh.clean(produce_merge_map=True)['PointMergeMap']
    regindicies = np.where(mapping[PML.n_points :] < PML.n_points)[0]
    PMLindicies = mapping[PML.n_points + regindicies]  # noqa: N806

    mesh.point_data['boundary'] = np.zeros(mesh.n_points, dtype=int) - 1
    mesh.point_data['boundary'][PMLindicies] = regindicies + PML.n_points
    mesh.point_data['boundary'][PML.n_points + regindicies] = PMLindicies

    indices = np.where(mesh.point_data['boundary'] > 0)[0]

    mesh['matTag'] = np.ones(mesh.n_cells, dtype=np.uint8)

    # define the ASDA absorbing elements
    if AbsorbingElements.lower() == 'asda':
        mesh = mesh.clean(tolerance=1e-6, remove_unused_points=False)
        mesh['ASDA_type'] = np.zeros(mesh.n_cells, dtype=np.uint8)

        ASDAelem_type = {  # noqa: N806
            'B': 1,
            'L': 2,
            'R': 3,
            'F': 4,
            'K': 5,
            'BL': 6,
            'BR': 7,
            'BF': 8,
            'BK': 9,
            'LF': 10,
            'LK': 11,
            'RF': 12,
            'RK': 13,
            'BLF': 14,
            'BLK': 15,
            'BRF': 16,
            'BRK': 17,
        }

        ASDAelem_typereverse = {  # noqa: N806
            1: 'B',
            2: 'L',
            3: 'R',
            4: 'F',
            5: 'K',
            6: 'BL',
            7: 'BR',
            8: 'BF',
            9: 'BK',
            10: 'LF',
            11: 'LK',
            12: 'RF',
            13: 'RK',
            14: 'BLF',
            15: 'BLK',
            16: 'BRF',
            17: 'BRK',
        }
        xmin, xmax, ymin, ymax, zmin, zmax = reg.bounds
        ASDA_xwidth = xmax - xmin  # noqa: N806
        ASDA_ywidth = ymax - ymin  # noqa: N806
        ASDA_zwidth = zmax - zmin  # noqa: N806
        # print("ASDA_xwidth", ASDA_xwidth)
        # print("ASDA_ywidth", ASDA_ywidth)
        # print("ASDA_zwidth", ASDA_zwidth)

        i = 0
        for ele_center in mesh.cell_centers().points:
            # check if the element is in the left or rightside
            if ele_center[0] < (-ASDA_xwidth / 2.0):
                # it is in the left side
                # check if it is in the front or back
                if ele_center[1] < (-ASDA_ywidth / 2.0):
                    # it is in the back
                    # check if it is in the bottom or top
                    if ele_center[2] < -ASDA_zwidth:
                        # it is in the bottom
                        mesh['ASDA_type'][i] = ASDAelem_type['BLK']
                    else:
                        # it is in the top
                        mesh['ASDA_type'][i] = ASDAelem_type['LK']
                elif ele_center[1] > (ASDA_ywidth / 2.0):
                    # it is in the front
                    # check if it is in the bottom or top
                    if ele_center[2] < -ASDA_zwidth:
                        # it is in the bottom
                        mesh['ASDA_type'][i] = ASDAelem_type['BLF']
                    else:
                        # it is in the top
                        mesh['ASDA_type'][i] = ASDAelem_type['LF']
                else:  # noqa: PLR5501
                    # it is in the middle
                    # check if it is in the bottom or top
                    if ele_center[2] < -ASDA_zwidth:
                        # it is in the bottom
                        mesh['ASDA_type'][i] = ASDAelem_type['BL']
                    else:
                        # it is in the top
                        mesh['ASDA_type'][i] = ASDAelem_type['L']

            elif ele_center[0] > (ASDA_xwidth / 2.0):
                # it is in the right side
                # check if it is in the front or back
                if ele_center[1] < (-ASDA_ywidth / 2.0):
                    # it is in the back
                    # check if it is in the bottom or top
                    if ele_center[2] < -ASDA_zwidth:
                        # it is in the bottom
                        mesh['ASDA_type'][i] = ASDAelem_type['BRK']
                    else:
                        # it is in the top
                        mesh['ASDA_type'][i] = ASDAelem_type['RK']
                elif ele_center[1] > (ASDA_ywidth / 2.0):
                    # it is in the front
                    # check if it is in the bottom or top
                    if ele_center[2] < -ASDA_zwidth:
                        # it is in the bottom
                        mesh['ASDA_type'][i] = ASDAelem_type['BRF']
                    else:
                        # it is in the top
                        mesh['ASDA_type'][i] = ASDAelem_type['RF']
                else:  # noqa: PLR5501
                    # it is in the middle
                    # check if it is in the bottom or top
                    if ele_center[2] < -ASDA_zwidth:
                        # it is in the bottom
                        mesh['ASDA_type'][i] = ASDAelem_type['BR']
                    else:
                        # it is in the top
                        mesh['ASDA_type'][i] = ASDAelem_type['R']
            else:  # noqa: PLR5501
                # it is in the middle
                # check if it is in the front or back
                if ele_center[1] < (-ASDA_ywidth / 2.0):
                    # it is in the back
                    # check if it is in the bottom or top
                    if ele_center[2] < -ASDA_zwidth:
                        # it is in the bottom
                        mesh['ASDA_type'][i] = ASDAelem_type['BK']
                    else:
                        # it is in the top
                        mesh['ASDA_type'][i] = ASDAelem_type['K']
                elif ele_center[1] > (ASDA_ywidth / 2.0):
                    # it is in the front
                    # check if it is in the bottom or top
                    if ele_center[2] < -ASDA_zwidth:
                        # it is in the bottom
                        mesh['ASDA_type'][i] = ASDAelem_type['BF']
                    else:
                        # it is in the top
                        mesh['ASDA_type'][i] = ASDAelem_type['F']
                else:  # noqa: PLR5501
                    # it is in the middle
                    # check if it is in the bottom or top
                    if ele_center[2] < -ASDA_zwidth:
                        # it is in the bottom
                        mesh['ASDA_type'][i] = ASDAelem_type['B']

            i += 1

    if AbsorbingElements.lower() == 'normal':
        mesh = mesh.clean(tolerance=1e-6, remove_unused_points=False)
    #  =============================================================================
    # write the mesh
    # =============================================================================
    min_core = mesh.cell_data['partitioned'].min()
    max_core = mesh.cell_data['partitioned'].max()

    # write the  mesh nodes
    for core in range(min_core, max_core + 1):
        tmp = mesh.extract_cells(np.where(mesh.cell_data['partitioned'] == core)[0])
        f = open(Dir + '/Nodes' + str(core + structurecores) + '.tcl', 'w')  # noqa: SIM115, PTH123

        for i in range(tmp.n_points):
            f.write(
                f"node  [expr int($StructureMaxNodeTag + 1 + {tmp['vtkOriginalPointIds'][i]})] {tmp.points[i][0]} {tmp.points[i][1]} {tmp.points[i][2]}\n"
            )
        f.close()

    # writing the mesh elements
    if AbsorbingElements == 'ASDA':
        # writing the mesh elements
        for core in range(min_core, max_core + 1):
            tmp = mesh.extract_cells(
                np.where(mesh.cell_data['partitioned'] == core)[0]
            )
            f = open(Dir + '/Elements' + str(core + structurecores) + '.tcl', 'w')  # noqa: SIM115, PTH123
            if core >= reg_num_cores + DRM_num_cores:
                for eletag in range(tmp.n_cells):
                    tmpeletag = (
                        '[expr int($StructureMaxEleTag + 1 + '
                        + str(tmp['vtkOriginalCellIds'][eletag])
                        + ')]'
                    )
                    tmpNodeTags = [  # noqa: N806
                        f'[expr int($StructureMaxNodeTag + 1 + {x})]'
                        for x in tmp['vtkOriginalPointIds'][
                            tmp.get_cell(eletag).point_ids
                        ]
                    ]
                    Domainname = DomainNames[tmp['Domain'][eletag] - 1]  # noqa: N806
                    if Domainname == 'PML':
                        Domainname = 'Absorbing'  # noqa: N806
                    tmpmatTag = f"${Domainname}matTag{tmp['matTag'][eletag]}"  # noqa: N806
                    tmpASDA_type = ASDAelem_typereverse[tmp['ASDA_type'][eletag]]  # noqa: N806
                    f.write(
                        f"eval \"element $elementType {tmpeletag} {' '.join(tmpNodeTags)} {tmpmatTag} {tmpASDA_type}\" \n"
                    )
            else:
                for eletag in range(tmp.n_cells):
                    tmpeletag = (
                        '[expr int($StructureMaxEleTag + 1 + '
                        + str(tmp['vtkOriginalCellIds'][eletag])
                        + ')]'
                    )
                    tmpNodeTags = [  # noqa: N806
                        f'[expr int($StructureMaxNodeTag + 1 + {x})]'
                        for x in tmp['vtkOriginalPointIds'][
                            tmp.get_cell(eletag).point_ids
                        ]
                    ]
                    Domainname = DomainNames[tmp['Domain'][eletag] - 1]  # noqa: N806
                    tmpmatTag = f"${Domainname}matTag{tmp['matTag'][eletag]}"  # noqa: N806
                    f.write(
                        f"eval \"element $elementType {tmpeletag} {' '.join(tmpNodeTags)} {tmpmatTag}\" \n"
                    )
            f.close()
    else:
        for core in range(min_core, max_core + 1):
            tmp = mesh.extract_cells(
                np.where(mesh.cell_data['partitioned'] == core)[0]
            )
            f = open(Dir + '/Elements' + str(core + structurecores) + '.tcl', 'w')  # noqa: SIM115, PTH123
            for eletag in range(tmp.n_cells):
                tmpeletag = (
                    '[expr int($StructureMaxEleTag + 1 + '
                    + str(tmp['vtkOriginalCellIds'][eletag])
                    + ')]'
                )
                tmpNodeTags = [  # noqa: N806
                    f'[expr int($StructureMaxNodeTag + 1 + {x})]'
                    for x in tmp['vtkOriginalPointIds'][
                        tmp.get_cell(eletag).point_ids
                    ]
                ]
                Domainname = DomainNames[tmp['Domain'][eletag] - 1]  # noqa: N806
                if Domainname == 'PML':
                    Domainname = 'Absorbing'  # noqa: N806
                tmpmatTag = f"${Domainname}matTag{tmp['matTag'][eletag]}"  # noqa: N806
                f.write(
                    f"eval \"element $elementType {tmpeletag} {' '.join(tmpNodeTags)} {tmpmatTag}\" \n"
                )
            f.close()

    if AbsorbingElements == 'PML':
        # writing the boundary files
        for core in range(reg_num_cores + DRM_num_cores, max_core + 1):
            tmp = mesh.extract_cells(
                np.where(mesh.cell_data['partitioned'] == core)[0]
            )
            f = open(Dir + '/Boundary' + str(core + structurecores) + '.tcl', 'w')  # noqa: SIM115, PTH123
            for i in range(tmp.n_points):
                if tmp['boundary'][i] != -1:
                    x, y, z = tmp.points[i]
                    nodeTag1 = tmp['vtkOriginalPointIds'][i]  # noqa: N806
                    nodeTag2 = tmp['boundary'][i]  # noqa: N806
                    f.write(
                        f'node [expr int($StructureMaxNodeTag + 1 +{nodeTag2})] {str(x)} {str(y)} {str(z)}\n'  # noqa: RUF010
                    )
                    f.write(
                        f'equalDOF [expr int($StructureMaxNodeTag + 1 + {nodeTag2})] [expr int($StructureMaxNodeTag + 1 +{nodeTag1})] 1 2 3\n'
                    )

    # =============================================================================
    # printing information
    # =============================================================================
    print(f'Number of regular cores: {reg_num_cores}')  # noqa: T201
    print(f'Number of DRM cores: {DRM_num_cores}')  # noqa: T201
    print(f'Number of PML cores: {PML_num_cores}')  # noqa: T201
    print(  # noqa: T201
        f'Number of regular elements: {regular.n_cells} roughly {int(regular.n_cells/reg_num_cores)} each core'
    )
    print(  # noqa: T201
        f'Number of DRM elements: {DRM.n_cells} roughly {int(DRM.n_cells/DRM_num_cores)} each core'
    )
    print(  # noqa: T201
        f'Number of PML elements: {PML.n_cells} roughly {int(PML.n_cells/PML_num_cores)} each core'
    )
    print(f'Number of total elements: {mesh.n_cells}')  # noqa: T201
    print(f'Number of total points: {mesh.n_points}')  # noqa: T201
    print(f'Number of cores: {max_core-min_core+1}')  # noqa: T201
    print(f'Number of PML nodes: {PML.n_points}')  # noqa: T201
    print(f'Number of regular nodes: {regular.n_points}')  # noqa: T201
    print(f'Number of DRM nodes: {DRM.n_points}')  # noqa: T201
    if AbsorbingElements == 'PML':
        print(f'Number of MP constraints: {regindicies.size}')  # noqa: T201

    # calculating number of surface points on the boundaries
    eps = 1e-2
    bounds = np.array(mesh.bounds) - np.array([-eps, eps, -eps, eps, -eps, -eps])
    cube = pv.Cube(bounds=bounds)
    # points outside the cube
    selected = mesh.select_enclosed_points(cube, inside_out=True)
    pts = mesh.extract_points(
        selected['SelectedPoints'].view(bool),
        include_cells=False,
    )
    print(f'number of sp constraints: {pts.n_points*9}')  # noqa: T201

    # f = h5py.File('./DRMloadSmall.h5drm', 'r')
    if DRMinformation['DRM_Location'].lower() == 'local':
        f = h5py.File(DRMfile, 'r')
        pts = f['DRM_Data']['xyz'][:]
        internal = f['DRM_Data']['internal'][:]  # noqa: F841
        xyz0 = f['DRM_QA_Data']['xyz'][:]

    if (
        DRMinformation['DRM_Provider_Software'].lower() == 'shakermaker'
        and DRMinformation['DRM_Location'].lower() == 'local'
    ):
        pts = pts - xyz0
        pts[:, [0, 1]] = pts[:, [1, 0]]
        pts[:, 2] = -pts[:, 2]
        pts = pts * DRMinformation['crd_scale']

    if DRMinformation['DRM_Location'].lower() == 'local':
        set1 = DRM.points
        set2 = pts

        # check that set2 is a subset of set1
        tree = KDTree(set1)

        tolernace = 1e-6
        issubset = True
        for point in set2:
            dist, ind = tree.query(point, distance_upper_bound=tolernace)
            if dist > tolernace:
                issubset = False
                break

        if issubset:
            print('The DRM nodes in the loading file are subset of the DRM mesh')  # noqa: T201
        else:
            print('The DRM nodes in the loading file are not subset of the DRM mesh')  # noqa: T201
            print(  # noqa: T201
                'Please check the DRM nodes in the loading file or change the DRM mesh'
            )
    else:
        print('The DRM nodes are not checked for subset')  # noqa: T201

    pl = pv.Plotter()
    # plot the DRM layer with the DRM nodes loaded from the DRM file
    pl.add_mesh(DRM, scalars='partitioned', show_edges=True)
    if DRMinformation['DRM_Location'].lower() == 'local':
        pl.add_points(pts, color='r')
    pl.export_html(meshplotdir + '/DRM.html')
    pl.clear()

    # plot the regular mesh with the internal nodes loaded from the DRM file
    pl.add_mesh(regular, scalars='partitioned', show_edges=True)
    pl.export_html(meshplotdir + '/Regular.html')
    pl.clear()

    # plot the PML mesh
    pl.add_mesh(PML, scalars='partitioned', show_edges=True)
    pl.export_html(meshplotdir + '/PML.html')
    pl.clear()

    # plot the total mesh
    pl.add_mesh(mesh, scalars='partitioned', show_edges=True)
    pl.export_html(meshplotdir + '/Total_partitioned.html')
    pl.clear()

    # plot the total mesh with domain scalars
    pl.add_mesh(mesh, scalars='Domain', show_edges=True)
    pl.export_html(meshplotdir + '/Total_domain.html')
    pl.clear()

    if AbsorbingElements == 'ASDA':
        pl.add_mesh(mesh, scalars='ASDA_type', show_edges=True, cmap='tab20')
        pl.export_html(meshplotdir + '/ASDA_total.html')
        pl.clear()

        # filter the mesh with domain pml
        indices = mesh['Domain'] == info['PMLDomain']
        grid = mesh.extract_cells(indices)
        pl.add_mesh(grid, scalars='ASDA_type', show_edges=True, cmap='tab20b')
        pl.export_html(meshplotdir + '/ASDA_PML.html')
        pl.clear()

    pl.close()

    # save the mesh
    mesh.save(os.path.join(OutputDir, 'mesh.vtk'), binary=True)  # noqa: PTH118

    # return thenumber of elements
    return (mesh.n_cells, mesh.n_points)


# %%
