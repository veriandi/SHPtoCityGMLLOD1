#!/usr/bin/env python
# coding: utf-8

# In[27]:


# Import library yang diperlukan
import shapefile as sf
from lxml import etree
import uuid
import geopandas as gpd
from shapely.geometry import Polygon


# In[28]:


# Directory multipatch bangunan LOD1 Coblong
sfDir = '/Users/veriandi/Desktop/Projects/CityGML Coblong/Multipatch LOD1/3D_BDG_LOD1_att_extrd'


# In[29]:


# Directory shapefile persil Coblong
persilDir = '/Users/veriandi/Desktop/Projects/CityGML Coblong/Persil/persil.shp'


# In[30]:


# Membaca file persil dan memasukkannya ke dalam GeoDataFrame
Persil = gpd.read_file(persilDir)
persil = Persil.loc[:, ['NIB', 'geometry']]
persil = persil.to_crs('EPSG:32748')


# In[31]:


# Membaca file multipatch LOD1
# Ekstraksi geometri dan atribut
sfReader = sf.Reader(sfDir)
features = sfReader.shapes()
attributes = sfReader.records()


# In[33]:


# Ekstraksi koordinat XY dan Z yang disimpan dalam list berbeda
# Dilakukan untuk menentukan building footprint dan ketinggian bangunan
FeatXYCoords = []
FeatZCoords = []
for feature in features:
    XYCoords = []
    ZCoords = []
    xy = feature.points
    z = feature.z
    for n in range(len(feature.parts)):
        if n != len(feature.parts)-1:
            PartXYCoords = xy[feature.parts[n]:feature.parts[n+1]]
            PartZCoords = z[feature.parts[n]:feature.parts[n+1]]
            XYCoords.append(PartXYCoords)
            ZCoords.append(PartZCoords)
        elif n == len(feature.parts)-1:
            PartXYCoords = xy[feature.parts[n]:]
            PartZCoords = z[feature.parts[n]:]
            XYCoords.append(PartXYCoords)
            ZCoords.append(PartZCoords)
    FeatXYCoords.append(XYCoords)
    FeatZCoords.append(ZCoords)
    
FeatXYZCoords = []
for i, feature in enumerate(FeatXYCoords):
    XYZFeat = []
    for n, surface in enumerate(feature):
        XYZSurf = []
        for m, xy in enumerate(surface):
            l_coord = list(xy)
            l_coord.append(FeatZCoords[i][n][m])
            t_coord = tuple(l_coord)
            XYZSurf.append(t_coord)
        XYZFeat.append(XYZSurf)
    FeatXYZCoords.append(XYZFeat)


# In[34]:


# Perhitungan ketinggian dasar bangunan untuk proses seleksi building footprint
# Perhitungan ketinggian bangunan untuk dijadikan acuan ketinggian dalam proses ektrusi bangunan
ZMinValues = []
BuildingHeight = []
for ZFeatures in FeatZCoords:
    ZValues = []
    for surface in ZFeatures:
        for z in surface:
            ZValues.append(z)
    ZMinValues.append(min(ZValues))
    BuildingHeight.append(max(ZValues)-min(ZValues))


# In[35]:


# Seleksi building footprint untuk setiap bangunan
GroundSurfaces = []
for i, feature in enumerate(FeatXYZCoords):
    GroundSurface = []
    for surface in feature:
        ZValues = []
        for m, xyz in enumerate(surface):
            ZValues.append(xyz[2])
        ZMin = ZMinValues[i]
        ZAvg = sum(ZValues)/len(ZValues)
        if ZMin == ZAvg:
            GroundSurface.append(surface)
    GroundSurfaces.append(GroundSurface)


# In[36]:


# Memasukkan building footprint ke dalam GeoDataFrame
# Diperlukan untuk proses spatial join dengan GeoDataFrame persil
# Untuk mendapatkan informasi persil-persil yang berpotongan dengan building footprint setiap bangunan
dfGround = gpd.GeoDataFrame(columns=['geometry'])
for i, surface in enumerate(GroundSurfaces):
    if len(surface) != 0:
        dfGround.loc[i] = Polygon(surface[0])
    elif len(surface) == 0:
        dfGround.loc[i] = None
dfGround = dfGround.set_crs('EPSG:32748')


# In[37]:


# Spatial join building footprint dengan persil
groundSJoin = gpd.sjoin(dfGround, persil, how="left", op='intersects')


# In[38]:


# Ekstraksi NIB persil yang berpotongan pada setiap building footprint
NIB = {}
for i, row in groundSJoin.iterrows():
    if i not in NIB.keys():
        NIB[i] = [row['NIB']]
    elif i in NIB.keys():
        NIB[i].append(row['NIB'])


# In[39]:


# Mengekstrusi dinding dan membuat atap untuk seluruh bangunan
# Mengacu ke pada building footprint dan ketinggian
# Disimpan di dalam dictionary
OutputDict = {}
ID = 0
for i, ground in enumerate(GroundSurfaces):
    ID += 1
    OutputDict['IDLOD1_{}'.format(ID)] = []
    
    if len(ground) == 1:
        XYCoordinates = []
        XYZCoordinates = ground[0].copy()
        for coordinate in XYZCoordinates:
            t_coord = (coordinate[0], coordinate[1])
            XYCoordinates.append(t_coord)
        if sf.signed_area(XYCoordinates) < 0:
            XYZCoordinates.reverse()
        
        Ground = ground[0].copy()
        if sf.signed_area(XYCoordinates) >= 0:
            Ground.reverse()
        OutputDict['IDLOD1_{}'.format(ID)].append(Ground)
        
        for n in range(len(XYZCoordinates)-1):
            coord1 = list(XYZCoordinates[n])
            coord2 = list(XYZCoordinates[n+1])
            coord3 = [coord2[0], coord2[1], coord2[2] + BuildingHeight[i]]
            coord4 = [coord1[0], coord1[1], coord1[2] + BuildingHeight[i]]
            surface = [tuple(coord1), tuple(coord2), tuple(coord3), tuple(coord4), tuple(coord1)]
            OutputDict['IDLOD1_{}'.format(ID)].append(surface)
            
        Roof = []
        for coordinate in XYZCoordinates:
            t_coord = (coordinate[0], coordinate[1], coordinate[2] + BuildingHeight[i])
            Roof.append(t_coord)
        OutputDict['IDLOD1_{}'.format(ID)].append(Roof)


# In[40]:


# Mendefinisikan namespace CityGML
ns_base = "http://www.citygml.org/citygml/profiles/base/2.0"
ns_core = "http://www.opengis.net/citygml/2.0"
ns_bldg = "http://www.opengis.net/citygml/building/2.0"
ns_gen = "http://www.opengis.net/citygml/generics/2.0"
ns_gml = "http://www.opengis.net/gml"
ns_xAL = "urn:oasis:names:tc:ciq:xsdschema:xAL:2.0"
ns_xlink = "http://www.w3.org/1999/xlink"
ns_xsi = "http://www.w3.org/2001/XMLSchema-instance"
ns_schemaLocation = "http://www.citygml.org/citygml/profiles/base/2.0 http://schemas.opengis.net/citygml/profiles/base/2.0/CityGML.xsd"

nsmap = {None : ns_base, 'core': ns_core, 'bldg': ns_bldg, 'gen': ns_gen, 'gml': ns_gml, 'xAL': ns_xAL, 'xlink': ns_xlink, 'xsi': ns_xsi}


# In[41]:


# Membuat root element CityGML (CityModel)
CityModel = etree.Element("{%s}CityModel" % ns_core, nsmap=nsmap)
CityModel.set('{%s}schemaLocation' % ns_xsi, ns_schemaLocation)


# In[42]:


# Membuat deskripsi dari file/model
description = etree.SubElement(CityModel, '{%s}description' % ns_gml)
description.text = 'Coblong LOD 1 Buildings'


# In[43]:


# Mendefinisikan fungsi untuk kalkulasi bounding box
def bounding_box(surfaces):
    coorX = []
    coorY = []
    coorZ = []
    for surface in surfaces:
        for coordinate in surface:
            coorX.append(coordinate[0])
            coorY.append(coordinate[1])
            coorZ.append(coordinate[2])
    lowerCorner = [min(coorX), min(coorY), min(coorZ)]
    upperCorner = [max(coorX), max(coorY), max(coorZ)]
    return lowerCorner, upperCorner


# In[44]:


# Kalkulasi bounding box untuk model
xValues = []
yValues = []
zValues = []
for i, ID in enumerate(OutputDict.keys()):
    if len(OutputDict[ID]) != 0:
        lower, upper = bounding_box(OutputDict[ID])
        xValues.append(lower[0])
        xValues.append(upper[0])
        yValues.append(lower[1])
        yValues.append(upper[1])
        zValues.append(lower[2])
        zValues.append(upper[2])
        
lower = [min(xValues), min(yValues), min(zValues)]
upper = [max(xValues), max(yValues), max(zValues)]

crs = 'EPSG:32748'

BoundingBox = etree.SubElement(CityModel, '{%s}boundedBy' % ns_gml)
Envelope = etree.SubElement(BoundingBox, '{%s}Envelope' % ns_gml, srsDimension='3')
Envelope.set('srsName', crs)

lowCorner = etree.SubElement(Envelope, '{%s}lowerCorner' % ns_gml)
lowCorner.text = str(lower[0]) + ' ' + str(lower[1]) + ' ' + str(lower[2])
uppCorner = etree.SubElement(Envelope, '{%s}upperCorner' % ns_gml)
uppCorner.text = str(upper[0]) + ' ' + str(upper[1]) + ' ' + str(upper[2])


# In[45]:


# Mendefinisikan fungsi untuk menulis objek bangunan
def writing_solid(surfaces, CompSurfElem):
    for surface in surfaces:
        surf_uuid = 'UUID_' + str(uuid.uuid4()) + '_1'
        surfaceMember = etree.SubElement(CompSurfElem, '{%s}surfaceMember' % ns_gml)
        Polygon = etree.SubElement(surfaceMember, '{%s}Polygon' % ns_gml)
        Polygon.set('{%s}id' % ns_gml, surf_uuid + '_poly')
        exterior = etree.SubElement(Polygon, '{%s}exterior' % ns_gml)
        LinearRing = etree.SubElement(exterior, '{%s}LinearRing' % ns_gml)
        posList = etree.SubElement(LinearRing, '{%s}posList' % ns_gml, srsDimension='3')
        
        coordinates = ''
        copy = ''
        for coordinate in surface:
            coordinates = copy + str(coordinate[0]) + ' ' + str(coordinate[1]) + ' ' + str(coordinate[2]) + ' '
            copy = coordinates
        posList.text = coordinates[:-1]


# In[46]:


# Iterasi penulisan atribut dan geometri untuk seluruh bangunan
for i, ID in enumerate(OutputDict.keys()):
    if len(OutputDict[ID]) != 0:
        cityObjectMember = etree.SubElement(CityModel, '{%s}cityObjectMember' % ns_core)

        Building = etree.SubElement(cityObjectMember, '{%s}Building' % ns_bldg)
        Building.set('{%s}id' % ns_gml, str(ID))
        
        FCODE = etree.SubElement(Building, '{%s}stringAttribute' % ns_gen)
        FCODE.set('name', 'FCODE')
        FCODEVal = etree.SubElement(FCODE, '{%s}value' % ns_gen)
        FCODEVal.text = str(attributes[i][2])
        
        NAMOBJ = etree.SubElement(Building, '{%s}stringAttribute' % ns_gen)
        NAMOBJ.set('name', 'NAMOBJ')
        NAMOBJVal = etree.SubElement(NAMOBJ, '{%s}value' % ns_gen)
        NAMOBJVal.text = str(attributes[i][4])
        
        REMARK = etree.SubElement(Building, '{%s}stringAttribute' % ns_gen)
        REMARK.set('name', 'REMARK')
        REMARKVal = etree.SubElement(REMARK, '{%s}value' % ns_gen)
        REMARKVal.text = str(attributes[i][5])
        
        UPDATED = etree.SubElement(Building, '{%s}stringAttribute' % ns_gen)
        UPDATED.set('name', 'UPDATED')
        UPDATEDVal = etree.SubElement(UPDATED, '{%s}value' % ns_gen)
        UPDATEDVal.text = str(attributes[i][17])
        
        KECAMATAN = etree.SubElement(Building, '{%s}stringAttribute' % ns_gen)
        KECAMATAN.set('name', 'KECAMATAN')
        KECAMATANVal = etree.SubElement(KECAMATAN, '{%s}value' % ns_gen)
        KECAMATANVal.text = str(attributes[i][19])
        
        NIBElem = etree.SubElement(Building, '{%s}stringAttribute' % ns_gen)
        NIBElem.set('name', 'NIB')
        NIBVal = etree.SubElement(NIBElem, '{%s}value' % ns_gen)
        NIBValues = ''
        if len(NIB[i]) != 0:
            for code in NIB[i]:
                NIBValues = NIBValues + str(code) + ' '
            NIBVal.text = NIBValues[:-1]
        
        MeasHeight = etree.SubElement(Building, '{%s}measuredHeight' % ns_bldg)
        MeasHeight.set('uom', 'meter')
        MeasHeight.text = str(attributes[i][12])

        lod1Solid = etree.SubElement(Building, '{%s}lod1Solid' % ns_bldg)
        Solid = etree.SubElement(lod1Solid, '{%s}Solid' % ns_gml)
        exterior = etree.SubElement(Solid, '{%s}exterior' % ns_gml)
        CompositeSurface = etree.SubElement(exterior, '{%s}CompositeSurface' % ns_gml)

        #iterasi penulisan semua surface ke dalam CompositeSurface
        writing_solid(OutputDict[ID], CompositeSurface)


# In[26]:


# Menuliskan model CityGML
output_dir = '/Users/veriandi/Desktop/LOD1 Coblong (EPSG 32748) Corrected .gml'
etree.ElementTree(CityModel).write(output_dir, xml_declaration=True, encoding='utf-8', pretty_print= True)

