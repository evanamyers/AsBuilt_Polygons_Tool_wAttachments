"""
This code is used in the AsBuilt Polygon tool for ArcGIS Pro.  It automates the creation of the polygons around selected
Points and Lines.  It also completes the Source and AsBuilt Date fields with values the user provides.
"""
import arcpy
import os
import sys
from shapely.geometry import Point, Polygon, LineString
import geopandas

arcpy.SetLogMetadata(False)
arcpy.SetLogHistory(False)
arcpy.env.overwriteOutput = True
arcpy.env.addOutputsToMap = False
# sys.tracebacklimit = 0

# return selLayers
def checkFeatureSelection():
    print("Checking Production layers.")
    # arcpy.AddMessage("Checking Production layers.")

    # Get list of all feature Layers
    mapLayers = []
    for lyr in lyrList:
        if lyr.visible:
            if lyr.isGroupLayer:
                # For group layers, check if the sublayer is visible
                for sublayer in lyr.listLayers():
                    if sublayer.visible:
                        if sublayer.isFeatureLayer:
                            print(f"The layer '{sublayer.longName}' is visible.")
                            mapLayers.append(sublayer.longName)
            try:
                if lyr.isGroupLayer and lyr.parentGroup:
                    if lyr.isFeatureLayer:
                        print(f"The layer '{lyr.longName}' is visible.")
                        mapLayers.append(lyr.longName)
            except AttributeError:
                continue
            if lyr.isFeatureLayer:
                print(f"The layer '{lyr.longName}' is visible.")
                mapLayers.append(lyr.longName)

    # Remove from list if it matches any of the criteria below:
    for each in mapLayers[:]:
        remove = False
        try:
            desc = arcpy.Describe(each)
            descPath = str(desc.catalogPath.lower())
            workspace = descPath.split('.sde')[0] + '.sde'
            descWS = arcpy.Describe(workspace)
            cp = descWS.connectionProperties
            fcFields = [f.name for f in arcpy.ListFields(each)]
            if cp.version == 'sde.DEFAULT':
                remove = True
            if 'SOURCE' not in fcFields:
                remove = True
            if 'ASBUILTDATE' not in fcFields:
                remove = True
            if all(item not in descPath for item in ['wud.sewerstormwater', 'wud.waterdistribution']):
                remove = True
            if 'rest/services/' in descPath:
                remove = True
            if "WATERTYPE" not in fcFields:
                remove = True
        except (AttributeError, OSError):
            remove = True
        if remove:
            mapLayers.remove(each)

    # Get a list of selected layers:
    selLayers = []
    for lyr in mapLayers:
        desclayer = arcpy.Describe(lyr)
        if desclayer.FIDset != '':
            if lyr not in selLayers:
                # featureCount = len(desc.FIDSet.split(";"))
                selLayers.append(lyr)

    if not selLayers:
        raise ValueError("Make sure at least 1 feature is selected is selected or check if you are using"
                         "'Default' data; this tool is intended for versioned data.")
        # sys.exit()

    else:
        print("Production layers selected.")
        # arcpy.AddMessage("Production layers selected.")

    arcpy.AddMessage(selLayers)
    return selLayers


def updateSelected(selLayers):

    print("Populating SOURCE and ASBUILTDATE fields for selected features.")
    arcpy.AddMessage("Populating SOURCE and ASBUILTDATE fields for selected features.")
    # Fill out SOURCE and ASBUILTDATE fields for the selected features
    # (this step is not for the as-built polygons, thats later)
    selDesc = arcpy.Describe(selLayers[0])
    workspace = os.path.dirname(selDesc.catalogPath)
    desc = arcpy.Describe(workspace)
    if hasattr(desc, "datasetType") and desc.datasetType == 'FeatureDataset':
        workspace = os.path.dirname(workspace)
    with arcpy.da.Editor(workspace, multiuser_mode=selDesc.isVersioned):
        for eachlayer in selLayers:
            # desc = arcpy.Describe(eachlayer)
            # FID = desc.FIDSet
            # if FID:
            with arcpy.da.UpdateCursor(eachlayer, ['SOURCE', 'ASBUILTDATE']) as cursor:
                for row in cursor:
                    if row[0] != r"{}".format(hyperlink) or row[1] != asbuiltDate:
                        row[0] = r"{}".format(hyperlink)
                        row[1] = asbuiltDate
                        cursor.updateRow(row)


# return dissolvedBuffer, asBuiltBuffers
def createBuffers(selLayers):

    arcpy.env.workspace = aprx.defaultGeodatabase
    workspace = arcpy.env.workspace
    # workspace = arcpy.env.scratchGDB
    # arcpy.env.scratchWorkspace = workspace

    asbuiltNo = os.path.splitext(os.path.basename(pbcwudfile))[0][0:7]
    p56 = hyperlink.split("\\")[2]
    # if the 5th position is an underscore, it's an assumed asbuilt number
    if pbcwudfile[4] == '_':
        # get first 4 characters of filename
        asbuiltNo = os.path.splitext(os.path.basename(pbcwudfile))[0][0:4]


    fields = ['PBCWUDFILE', 'HYPERLINK', 'P56FOLDER', 'ASBUILTNO', 'ASBUILTDATE',
              'WUDPROJECTNUM', 'WATER', 'SEWER', 'RECLAIMED', 'RAW', 'OTHER',
              'LifeCycleStatusRemoved', 'SHAPE@']

    # Create asBuiltBuffers:
    print("Checking if asBuiltBuffer layer exists.  If it does, clear the table.")
    asBuiltBuffers = arcpy.CreateFeatureclass_management(workspace, "asBuiltBuffers", 'POLYGON', lyrdescPath,
                                                         'SAME_AS_TEMPLATE', 'SAME_AS_TEMPLATE', '2236')

    print("Creating Buffers for the selected features:")
    with arcpy.da.Editor(workspace, multiuser_mode=False):
        for each in selLayers:
            desc = arcpy.Describe(each)
            try:
                FID = desc.FIDSet
            except():
                continue
            if FID:
                print("Making buffer for: {}".format(each))  # desc.name
                arcpy.AddMessage("Making buffer for: {}".format(each))  # desc.name
                sqlquery = "OBJECTID IN ({0})".format(FID.replace(';', ','))
                fieldsWaterType = {"WATER": "Potable", "SEWER": "Sewage", "RECLAIMED": "Reclaimed", "RAW": "Raw",
                                   "OTHER": "Treated"}
                if desc.shapeType == 'Polyline':
                    insertCursor = arcpy.da.InsertCursor(asBuiltBuffers, fields)
                    with arcpy.da.SearchCursor(each, ["WATERTYPE", "SHAPE@"],
                                               where_clause=sqlquery) as search_cursor:
                        for row in search_cursor:
                            lineCoords = []
                            for vert in row[1]:
                                for coord in vert:
                                    lineCoords.append((coord.X, coord.Y))
                                gisLine = [LineString(lineCoords)]
                            lineBuffer = {'PBCWUDFILE': pbcwudfile, 'HYPERLINK': hyperlink,
                                           'P56FOLDER': p56, 'ASBUILTNO': asbuiltNo,
                                           'ASBUILTDATE': asbuiltDate, 'WUDPROJECTNUM': asbuiltWUDNUM,
                                           'WATER': 'No', 'SEWER': 'No',
                                           'RECLAIMED': 'No', 'RAW': 'No', 'OTHER': 'No',
                                           'LifeCycleStatusRemoved': 'No', 'SHAPE@': gisLine}
                            lineDict = {"WATERTYPE": row[0], "Shape": row[1]}
                            waterTypeDict = {}
                            for output_field, input_value in fieldsWaterType.items():
                                waterTypeDict[output_field] = "Yes" if lineDict["WATERTYPE"] == input_value else "No"
                            for key, value in waterTypeDict.items():
                                if value == 'Yes':
                                    for att, values in lineBuffer.items():
                                        if att == key:
                                            lineBuffer[att] = 'Yes'

                            gdf = geopandas.GeoDataFrame(lineBuffer, geometry='SHAPE@', crs='EPSG:2236')
                            gdf['SHAPE@'] = gdf['SHAPE@'].buffer(int(buffersize))

                            bufferCoords = gdf['SHAPE@'].apply(
                                lambda geom: list(geom.exterior.coords) if geom.is_empty is False else [])
                            for idx, coordList in enumerate(bufferCoords):
                                bufferPoly = Polygon(coordList)

                            lineBuffer['SHAPE@'] = coordList

                            rowValues = [lineBuffer[field] for field in fields]
                            insertCursor.insertRow(rowValues)

                if desc.shapeType == 'Point':
                    insertCursor = arcpy.da.InsertCursor(asBuiltBuffers, fields)
                    with arcpy.da.SearchCursor(each, ["WATERTYPE", "SHAPE@XY"],
                                               where_clause=sqlquery) as search_cursor:
                        for row in search_cursor:
                            pointBuffer = {'PBCWUDFILE': pbcwudfile, 'HYPERLINK': hyperlink,
                                           'P56FOLDER': p56, 'ASBUILTNO': asbuiltNo,
                                           'ASBUILTDATE': asbuiltDate, 'WUDPROJECTNUM': asbuiltWUDNUM,
                                           'WATER': 'No', 'SEWER': 'No',
                                           'RECLAIMED': 'No', 'RAW': 'No', 'OTHER': 'No',
                                           'LifeCycleStatusRemoved': 'No', 'SHAPE@': [Point([row[1]])]}
                            pointDict = {"WATERTYPE": row[0], "Shape": row[1]}
                            waterTypeDict = {}
                            for output_field, input_value in fieldsWaterType.items():
                                waterTypeDict[output_field] = "Yes" if pointDict["WATERTYPE"] == input_value else "No"
                            for key, value in waterTypeDict.items():
                                if value == 'Yes':
                                    for att, values in pointBuffer.items():
                                        if att == key:
                                            pointBuffer[att] = 'Yes'

                            gdf = geopandas.GeoDataFrame(pointBuffer, geometry='SHAPE@', crs='EPSG:2236')
                            gdf['SHAPE@'] = gdf['SHAPE@'].buffer(int(buffersize))
                            arcpy.AddMessage(gdf)

                            bufferCoords = gdf['SHAPE@'].apply(
                                lambda geom: list(geom.exterior.coords) if geom.is_empty is False else [])
                            for idx, coordList in enumerate(bufferCoords):
                                bufferPoly = Polygon(coordList)

                            pointBuffer['SHAPE@'] = coordList

                            rowValues = [pointBuffer[field] for field in fields]
                            insertCursor.insertRow(rowValues)

                else:
                    pass

        print("Populating other required fields for buffer.")
        # Go through all the polygons, if their hyperlink is the same, update their 'watertype' fields to share 'Yes' values
        with arcpy.da.SearchCursor(asBuiltBuffers,
                                   ['HYPERLINK', 'SHAPE@', 'WATER', 'SEWER', 'RECLAIMED', 'RAW', 'OTHER']) as bufferList:
            for buffer in bufferList:
                keyBuffer = buffer[0]
                if buffer[2] == 'Yes' and buffer[3] == 'Yes':
                    pass
                else:
                    if "'" in keyBuffer:
                        sqlQuery1 = """HYPERLINK = '{}'""".format(keyBuffer.replace("'", "''"))
                    else:
                        sqlQuery1 = """HYPERLINK = '{}'""".format(keyBuffer)
                    print("Populating buffer {}".format(keyBuffer))
                    sel_values = []
                    try:
                        with arcpy.da.SearchCursor(asBuiltBuffers,
                                                   ['OBJECTID', 'HYPERLINK', 'WATER', 'SEWER', 'RECLAIMED', 'RAW', 'OTHER'],
                                                   sqlQuery1) as cursor:
                            for row in cursor:
                                if row not in sel_values:
                                    sel_values.append(row)

                                checkListWater = []
                                checkListSewer = []
                                checkListReclaimed = []
                                checkListRaw = []
                                checkListOther = []
                                for eachType in sel_values:
                                    if eachType[2] == 'Yes':
                                        checkListWater.append('Yes')
                                    if eachType[3] == 'Yes':
                                        checkListSewer.append('Yes')
                                    if eachType[4] == 'Yes':
                                        checkListReclaimed.append('Yes')
                                    if eachType[5] == 'Yes':
                                        checkListRaw.append('Yes')
                                    if eachType[6] == 'Yes':
                                        checkListOther.append('Yes')
                                # print(checkListWater, checkListSewer)
                        with arcpy.da.UpdateCursor(asBuiltBuffers, ['WATER', 'SEWER', 'RECLAIMED', 'RAW', 'OTHER'],
                                                   sqlQuery1) as cursor1:
                            for each1 in cursor1:
                                if checkListWater:
                                    each1[0] = 'Yes'
                                    cursor1.updateRow(each1)
                                if checkListSewer:
                                    each1[1] = 'Yes'
                                    cursor1.updateRow(each1)
                                if checkListReclaimed:
                                    each1[2] = 'Yes'
                                    cursor1.updateRow(each1)
                                if checkListRaw:
                                    each1[3] = 'Yes'
                                    cursor1.updateRow(each1)
                                if checkListOther:
                                    each1[4] = 'Yes'
                                    cursor1.updateRow(each1)

                    except():
                        pass

    print("Dissolving Buffers")
    dissolvedBufferPath = workspace + "\\asBuiltBuffer_dissolved"

    dissolvedBuffer = arcpy.management.Dissolve(asBuiltBuffers, dissolvedBufferPath,
                                                "PBCWUDFILE;HYPERLINK;P56FOLDER;ASBUILTNO;ASBUILTDATE;WUDPROJECTNUM;"
                                                "WATER;SEWER;RECLAIMED;RAW;OTHER;LifeCycleStatusRemoved",
                                                None, "MULTI_PART", "DISSOLVE_LINES", '')

    del insertCursor

    return dissolvedBuffer


def addNewPolygons(dissolvedBuffer, abPoly):

    arcpy.env.addOutputsToMap = True
    abDesc = arcpy.Describe(abPoly)
    arcpy.AddMessage("Adding new polygons.")
    workspace = os.path.dirname(arcpy.Describe(abPoly).catalogPath)
    desc = arcpy.Describe(workspace)
    if hasattr(desc, "datasetType") and desc.datasetType == 'FeatureDataset':
        workspace = os.path.dirname(workspace)
    with arcpy.da.Editor(workspace, multiuser_mode=abDesc.isVersioned):
        lstFields = [field.name for field in arcpy.ListFields(dissolvedBuffer) if field.name not in ['SHAPE_Length', 'SHAPE_Area']]
        lstFields.append('SHAPE@')
        targetCursor = arcpy.da.InsertCursor(abPoly, lstFields)

        with arcpy.da.SearchCursor(dissolvedBuffer, lstFields) as cursor:
            for row in cursor:
                targetCursor.insertRow(row)
        del targetCursor

    del dissolvedBuffer


def addAttachment():

    # Get the ID of the new polygon (work is done in version so no worry of conflict)
    # This part only searches the last row, minimizing time spent
    # with arcpy.da.SearchCursor(abPoly, ["OID@", "GLOBALID"], sql_clause=(None, 'ORDER BY OBJECTID DESC')) as cursor:
    #     newAbPolyID = cursor.next()
    dataSource = lambda abPoly: arcpy.Describe(abPoly).catalogPath
    with arcpy.da.SearchCursor(dataSource(abPoly), ["OID@", "GLOBALID"], sql_clause=(None, 'ORDER BY created_date DESC')) as cur:
        newAbPolyID = cur.next()

    print(newAbPolyID)

    # arr = arcpy.da.FeatureClassToNumPyArray(abPoly, ["OID@", "GLOBALID"])

    arcpy.env.workspace = lyrworkspace

    arcpy.AddMessage(newAbPolyID[0])
    arcpy.AddMessage(newAbPolyID[1])

    abDesc = arcpy.Describe(abPoly)
    arcpy.AddMessage("Adding attachments.")
    workspace = os.path.dirname(arcpy.Describe(abPoly).catalogPath)
    desc = arcpy.Describe(workspace)
    if hasattr(desc, "datasetType") and desc.datasetType == 'FeatureDataset':
        workspace = os.path.dirname(workspace)
    with arcpy.da.Editor(workspace, multiuser_mode=abDesc.isVersioned):
        sqlquery = f"OBJECTID = {newAbPolyID[0]}"
        with arcpy.da.InsertCursor(f"{abDesc.Name}__ATTACH",
                                   ["DATA", "ATT_NAME", "ATTACHMENTID", "REL_GLOBALID"]) as cursor:
            with open(asbuiltSourceRaw, 'rb') as file:
                binary_data = file.read()
                cursor.insertRow([binary_data, pbcwudfile, newAbPolyID[0], newAbPolyID[1]])


def do_stuff():

    if selLayers:

        updateSelected(selLayers)
        dissolvedBuffer = createBuffers(selLayers)
        addNewPolygons(dissolvedBuffer, abPoly)
        if addAttach == 1:
            addAttachment()
        # Refresh the layer
        arcpy.management.ApplySymbologyFromLayer(abPoly, abPoly, update_symbology="MAINTAIN")

    else:
        arcpy.AddMessage("Nothing selected")




if __name__ == '__main__':

    try:

        asbuiltSourceRaw = arcpy.GetParameterAsText(0)
        asbuiltDateRaw = arcpy.GetParameterAsText(1)
        asbuiltWUDNUMinput = arcpy.GetParameterAsText(2)
        asbuiltWUDNUM = None if asbuiltWUDNUMinput is '' else asbuiltWUDNUMinput
        buffersize = arcpy.GetParameter(3)  # + " Feet"
        addAttach = arcpy.GetParameter(4)

        asbuiltDateinput = asbuiltDateRaw.split(' ')[0]
        asbuiltDate = None if asbuiltDateinput is '' else asbuiltDateinput

        hyperlink = r"{}".format(asbuiltSourceRaw.replace(asbuiltSourceRaw.split('originals')[0], '..\\'))
        arcpy.AddMessage(hyperlink)
        pbcwudfile = os.path.basename(hyperlink)

        # List layers in currently opened map in project
        aprx = arcpy.mp.ArcGISProject('current')
        currentMap = aprx.activeMap
        lyrList = currentMap.listLayers()

        abPoly = ()
        for lyr in lyrList:
            if lyr.isFeatureLayer:
                try:
                    lyrdesc = arcpy.Describe(lyr)
                    if lyrdesc.Name == 'wGISRef.WUD.Asbuilt_Polygons':
                        lyrdescPath = lyrdesc.catalogPath
                        lyrworkspace = lyrdescPath.split('.sde')[0] + '.sde'
                        lyrdescWS = arcpy.Describe(lyrworkspace)
                        lyrcp = lyrdescWS.connectionProperties
                        # arcpy.AddMessage(lyrdescPath)
                        if (lyrcp.server).lower() == 'gisagl' and (lyrcp.database).lower() == 'wgisref':  # if (lyrcp.version).lower() != 'sde.default'
                            abPoly = lyr.longName
                            break
                except (OSError, AttributeError):
                    continue

        if abPoly:
            # arcpy.AddMessage("Found As-Built Polygon layer")
            print("Found As-Built Polygon layer")

        else:
            raise ValueError("An Asbuilt Polygons layer from the GISagl_wGISRef database is not in the current map.  "
                             "If it is in the map, make sure it is NOT the Default version.  "
                             "Also, to avoid another versioning error, the layers you want to modify must be versioned.")

        selLayers = checkFeatureSelection()

        do_stuff()

        del abPoly, lyrList, currentMap, aprx

    except Exception as e:
        arcpy.AddError(f"An error occurred: {str(e)}")

    finally:
        print('finished')
