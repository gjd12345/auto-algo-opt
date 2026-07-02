package main

import (
	//"runtime"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"math"
	"math/rand"
	"os"

	//"unsafe"
	"runtime"
	"strconv"
	"time"

	"go.uber.org/zap"
	"go.uber.org/zap/zapcore"
)

const (
	MAXASSIGNS   = 64
	MAXSHIPS     = 8
	MEMORYSIZE   = 16
	MAXINSERTION = 512
	SA_STEPS     = 32
	HEAT_MAX     = 1000
)

// BASIC FUNCTION
func Abs(x int) int {
	if x < 0 {
		return -x
	} else {
		return x
	}
}

type Ship struct {
	Id   int
	Ori  int
	Des  int
	Load int
}

// 车辆分配信息
type Assign struct {
	RoutingTask
	/*
	   Stations       [MAXASSIGNS]Station `json:"stations"`
	   Speed          float64   `json:"speed"`
	   TimeCurrent    float64   `json:"timeCurrent"`
	   StationCurrent Station   `json:"stationCurrent"`
	   LoadCurrent    float64   `json:"loadCurrent"`
	   LoadCap        float64   `json:"loadCap"`
	*/
	RoutingResult
	/*
	   Iteration int                 `json:"iter"`
	   ConsEval  int                 `json:"consEval"`
	   Cost      float64             `json:"cost"`
	   Results   [MAXASSIGNS]RoutingStackState `json:"results"`
	*/
	NextSta         int
	NextTime        int
	StaIndexes      [MAXSHIPS]Ship
	StaIndexesLen   int
	AccumulatedCost float64
	// -1 stand for the removed station
}

// ########################################################################
// #                            Assign Method                             #
// ########################################################################
// 打印Assign的所有信息
func (assign *Assign) PrettyPrint() {
	if assign.StationsLen > 0 {
		fmt.Println("======Assign Start======")
		fmt.Println("CurrentStation:")
		fmt.Println(assign.StationCurrent)
		fmt.Println("Stations:")
		fmt.Println(assign.Stations[:assign.StationsLen])
		fmt.Println("Staindex:")
		fmt.Println(assign.StaIndexes[:assign.StaIndexesLen])
		fmt.Printf("Cost:%f, CT:%d, NT:%d, NS:%d\n", assign.Cost, assign.TimeCurrent, assign.NextTime, assign.NextSta)
		fmt.Println("=======Assign End=======")
	} else {
		fmt.Println("Stations", assign)
	}
}

// 生成站点的reqcode
func (assign *Assign) GenSeq() {
	// 现将reqcode全部归零
	for ii := 0; ii < assign.StationsLen; ii++ {
		assign.Stations[ii].ReqCode = 0
	}
	// 再增加对应的req
	for ii := 0; ii < assign.StaIndexesLen; ii++ {
		if assign.StaIndexes[ii].Ori != -1 && assign.StaIndexes[ii].Des != -1 {
			assign.Stations[assign.StaIndexes[ii].Des].ReqCode += 1 << assign.StaIndexes[ii].Ori
		}
	}
}

//生成站点的路径

// 移除已经没有订单的站点, 如果有载重则弹出警告
func (assign *Assign) PureDelSta(ind int) {
	if assign.Stations[ind].Load != 0 {
		fmt.Println("Warning!! removing station not empty")

	}
	if ind < assign.StationsLen {
		copy(assign.Stations[ind:assign.StationsLen-1], assign.Stations[ind+1:assign.StationsLen])
	}
	assign.StationsLen -= 1
}

// 仅移除订单号
func (assign *Assign) PureDelStaInd(ind int) {
	if ind < assign.StaIndexesLen {
		copy(assign.StaIndexes[ind:assign.StaIndexesLen-1], assign.StaIndexes[ind+1:assign.StaIndexesLen])
	}
	assign.StaIndexesLen -= 1
}

// 清除已经完成的或者已经锁定完成的订单
func (assign *Assign) ClearFinished() {
	var del_store []int = make([]int, 0, 64)
	for ii := 0; ii < assign.StaIndexesLen; ii++ {
		if assign.StaIndexes[ii].Ori == -1 && assign.StaIndexes[ii].Des == -1 {
			fmt.Println("Ship Finished: ", assign.StaIndexes[ii].Id)
			del_store = append(del_store, ii)
		}
	}
	//注意，由于订单编号在变，此处如果使用顺序则会造成订单重复
	for index := range del_store {
		assign.PureDelStaInd(del_store[len(del_store)-index-1])
	}
}

// 移除站点, 输入站点序号，移除该站点，并标记该站点的所有订单
func (assign *Assign) RemoveSta(ind int) {
	for ii := 0; ii < assign.StaIndexesLen; ii++ {
		//fmt.Println(index, value, ind)
		if assign.StaIndexes[ii].Ori == ind {
			assign.StaIndexes[ii].Ori = -1
		} else {
			if assign.StaIndexes[ii].Ori > ind {
				assign.StaIndexes[ii].Ori -= 1
			}
		}
		if assign.StaIndexes[ii].Des == ind {
			assign.StaIndexes[ii].Des = -1
		} else {
			if assign.StaIndexes[ii].Des > ind {
				assign.StaIndexes[ii].Des -= 1
			}
		}
	}
	assign.Stations[ind].Load = 0
	assign.PureDelSta(ind)
}

// 触发时间，输入现在的时刻time，触发到达站点
// 注意current是指锁定的下一站点
func (assign *Assign) TriggerTime(time int) {
	logger := zap.L().Named("Trigger")
	var trigger_count int = 0
	//触发到达下一个站点，如果下一个站点的时刻小于等于现在时刻
	for assign.TimeCurrent <= time && assign.StationsLen > 0 {
		trigger_count += 1
		//fmt.Printf("Trigger Count:%d; timeCurrent:%d; nextTime:%d, time:%d\n", trigger_count, assign.TimeCurrent, assign.NextTime, time)
		//此处锁定下一站点
		//TODO: 解决触发多个站点到达时的同步问题
		assign.TimeCurrent = assign.NextTime
		assign.StationCurrent = assign.Stations[assign.NextSta]
		assign.LoadCurrent += assign.Stations[assign.NextSta].Load
		assign.RemoveSta(assign.NextSta)
		assign.AccumulatedCost += assign.Route[0].Travel
		if assign.StationsLen > 0 {
			assign.GenRoute() //TODO: 在线移除相关站点，而不是重新生成路径
		} else {
			logger.Info("Route Empty", zap.Float64("accumulated", assign.AccumulatedCost))
		}
		//fmt.Println("lalalala", assign.TimeCurrent)
		if trigger_count > 1 && time > 0 {
			logger.Warn(
				"Non-zero Trigger",
				zap.Int("iter", trigger_count),
				zap.Int("CurrentT", assign.TimeCurrent),
				zap.Int("NextT", assign.NextTime),
				zap.Int("TriggerT", time),
			)
		}
	}
}

// 增加以个订单
func (assign *Assign) AddShip(id int, ori, des Station) bool {
	// Early exit: no room for more ships
	if assign.StaIndexesLen >= MAXSHIPS {
		return false
	}
	// Bounds check: we might need up to 2 new stations
	neededSlots := 0
	if assign.StationsLen+2 > MAXSTATIONS {
		// Check if ori/des already exist
		oriFound := false
		desFound := false
		for ii := 0; ii < assign.StationsLen; ii++ {
			if assign.Stations[ii].Equal(&ori) {
				oriFound = true
			}
			if assign.Stations[ii].Equal(&des) {
				desFound = true
			}
		}
		if !oriFound {
			neededSlots++
		}
		if !desFound {
			neededSlots++
		}
		if assign.StationsLen+neededSlots > MAXSTATIONS {
			return false
		}
	}
	ship := Ship{id, -1, -1, Abs(ori.Load)}
	for ii := 0; ii < assign.StationsLen; ii++ {
		if assign.Stations[ii].Equal(&ori) {
			ship.Ori = ii
			assign.Stations[ii].Load += ori.Load
		} else {
			if assign.Stations[ii].Equal(&des) {
				ship.Des = ii
				assign.Stations[ii].Load += des.Load
			}
		}
	}
	if ship.Ori == -1 {
		ship.Ori = assign.StationsLen
		assign.Stations[assign.StationsLen] = ori
		assign.StationsLen += 1
	}
	if ship.Des == -1 {
		ship.Des = assign.StationsLen
		assign.Stations[assign.StationsLen] = des
		assign.StationsLen += 1
	}
	assign.StaIndexes[assign.StaIndexesLen] = ship
	assign.StaIndexesLen += 1
	return true
}

// 移除一个订单
func (assign *Assign) RemoveShip(id int) {
	var ind int = -1
	assign.GenSeq() // TODO: modify seq on the fly
	for ii := 0; ii < assign.StaIndexesLen; ii++ {
		if assign.StaIndexes[ii].Id == id {
			ind = ii
			break
		}
	}
	if ind < 0 {
		return
	}
	if assign.StaIndexes[ind].Ori < 0 || assign.StaIndexes[ind].Des < 0 {
		assign.PureDelStaInd(ind)
		return
	}
	assign.Stations[assign.StaIndexes[ind].Ori].Load -= assign.StaIndexes[ind].Load
	assign.Stations[assign.StaIndexes[ind].Des].Load += assign.StaIndexes[ind].Load

	// 如果对应站点没有订单，则移除,这段代码使用load是否为0判断不够优雅精确
	if assign.Stations[assign.StaIndexes[ind].Ori].Load == 0 {
		assign.RemoveSta(assign.StaIndexes[ind].Ori)
	}
	if assign.Stations[assign.StaIndexes[ind].Des].Load == 0 {
		assign.RemoveSta(assign.StaIndexes[ind].Des)
	}
	// 移除订单
	assign.PureDelStaInd(ind)
}

func (assign *Assign) RandShip() (id int, ori, des Station) {
	var ind, count int
	var ori_station, des_station Station
	for ii := 0; ii < assign.StaIndexesLen; ii++ {
		if assign.StaIndexes[ii].Ori >= 0 && assign.StaIndexes[ii].Des >= 0 {
			count++
		}
	}
	if count <= 0 {
		return -1, ori_station, des_station
	}
	ind = rand.Intn(count)
	//fmt.Println("this is the random:", count, ind)
	count = -1
	for ii := 0; ii < assign.StaIndexesLen; ii++ {
		if assign.StaIndexes[ii].Ori >= 0 && assign.StaIndexes[ii].Des >= 0 {
			count++
		}
		if count == ind {
			ori_station = assign.Stations[assign.StaIndexes[ii].Ori]
			ori_station.Load = assign.StaIndexes[ii].Load

			des_station = assign.Stations[assign.StaIndexes[ii].Des]
			des_station.Load = -assign.StaIndexes[ii].Load
			return assign.StaIndexes[ii].Id, ori_station, des_station
		}
	}
	return -1, ori_station, des_station
}

func (assign *Assign) GenRoute() {
	assign.GenSeq()
	if assign.StationsLen > 0 {
		//不要超出最大
		if assign.StaIndexesLen < MAXSHIPS {
			route := RoutingTS(&assign.RoutingTask)
			assign.RoutingResult = route
			if assign.Cost >= 0 {
				assign.NextSta = assign.Route[0].CurSta
				assign.NextTime = assign.Route[0].CurTime
			}
		} else {
			assign.Cost = -1
		}
	} else {
		assign.Cost = 0
		assign.NextSta = -1
		assign.NextTime = -1
	}
}

func read_json(path string, v interface{}) error {
	jsonFile, err := os.Open(path)
	// if we os.Open returns an error then handle it
	if err != nil {
		fmt.Println(err)
		return err
	}
	fmt.Println("Successfully Opened user.json")
	byteValue, _ := ioutil.ReadAll(jsonFile)
	defer jsonFile.Close()
	err = json.Unmarshal(byteValue, v)
	return err
}

// FUNCTION FOR DISPATH
type Dispatch struct {
	Assigns         [MAXASSIGNS]Assign
	AssignsLen      int
	TotalCost       float64
	AccumulatedCost float64
}

// 初始化dispatch
func (dispatch *Dispatch) Init(template Assign) {
	for ii := 0; ii < MAXASSIGNS; ii++ {
		dispatch.Assigns[ii] = template
	}
}

// 计算总计里程
func (dispatch *Dispatch) RenewnTotalCost() {
	dispatch.TotalCost = 0
	dispatch.AccumulatedCost = 0
	for ii := 0; ii < dispatch.AssignsLen; ii++ {
		if dispatch.Assigns[ii].StationsLen > 0 {
			dispatch.TotalCost += dispatch.Assigns[ii].Cost
		}
		dispatch.AccumulatedCost += dispatch.Assigns[ii].AccumulatedCost
	}
}

func (dispatch *Dispatch) TriggerTime(time int) {
	var assign *Assign
	for ii := 0; ii < dispatch.AssignsLen; ii++ {
		assign = &dispatch.Assigns[ii]
		assign.TriggerTime(time)
	}
	dispatch.RenewnTotalCost()
}

// 实际上的初始化与插入订单，注意此处dispatch需要初始化为template
func InsertShips(dispatch Dispatch, oris, dess []Station, total_ship int) Dispatch {
	var rand_range [MAXASSIGNS]int
	var rand_limit int = 0 //记录有多少个有车的assign

	logger := zap.L().Named("Insert")

	// 生成随机序列 TODO: 有些车在时间触发过程中可能变空了
	for ii := range rand_range {
		rand_range[ii] = ii
		// 交换不空的解
		if ii < dispatch.AssignsLen && dispatch.Assigns[ii].StationsLen > 0 {
			rand_range[ii], rand_range[rand_limit] = rand_range[rand_limit], ii
			// 记录有多少个不空的解
			rand_limit += 1
		}
	}
	//由于不空的解都在前面，所以只需要打乱前面这部分
	rand.Shuffle(rand_limit, func(i, j int) {
		rand_range[i], rand_range[j] = rand_range[j], rand_range[i]
	})

	// 开始插入
	for jj := range oris {
		for _, ii := range rand_range {
			//尝试插入解
			if !dispatch.Assigns[ii].AddShip(total_ship+jj, oris[jj], dess[jj]) {

				dispatch.Assigns[ii].Cost = -1

			} else {
				dispatch.Assigns[ii].GenRoute()

			}
			//插入失败
			if dispatch.Assigns[ii].Cost < 0 {
				//fmt.Println("inserted but not avaliable")
				dispatch.Assigns[ii].RemoveShip(total_ship + jj)
				dispatch.Assigns[ii].GenRoute()
			} else {
				//如果插入成功，并且插入了一辆空车，那么扩展一辆车
				if ii >= dispatch.AssignsLen {
					dispatch.AssignsLen += 1
				}
				break
			}
			// 应当一定有一辆车能插入成功,否则第assignslen也插入失败的话，说明该订单插不进去
			if ii >= dispatch.AssignsLen {
				logger.Warn(
					"Cannot Insert",
					zap.Int("ship", total_ship+jj),
					zap.Int("non_empty", rand_limit),
					zap.Int("assigns_len", dispatch.AssignsLen),
				)
				fmt.Println(oris[jj], dess[jj])
				dispatch.Assigns[dispatch.AssignsLen].PrettyPrint()
				//dispatch.Assigns[dispatch.AssignsLen].AddShip(total_ship + jj, oris[jj], dess[jj])
				//checkDispatch(&dispatch)
				break
			}
		}
	}
	dispatch.RenewnTotalCost()
	//XXX: 调查发现,insertion不会改变累计里程，是别的东西删除了累计里程
	return dispatch
}

func Optimization(dispatch Dispatch, temperature float64) Dispatch {
	var a1, a2 int
	var delta, best_delta float64 //TODO: return best delta and assigns
	var best_dispatch Dispatch
	//assigns := dispatch.Assigns[:dispatch.AssignsLen]
	best_dispatch = dispatch
	//如果没有assign则直接退出
	if dispatch.AssignsLen == 0 {
		return best_dispatch
	}
	for ii := 0; ii < SA_STEPS; ii++ {
		a1 = rand.Intn(dispatch.AssignsLen)
		a2 = rand.Intn(dispatch.AssignsLen)
		if a1 == a2 {
			continue
		}
		ori_cost := dispatch.Assigns[a1].Cost + dispatch.Assigns[a2].Cost
		id, ori, des := dispatch.Assigns[a1].RandShip()
		//fmt.Println("random dispatch.Assigns[a1] dispatch.Assigns[a2]:", dispatch.Assigns[a1].StaIndexes, dispatch.Assigns[a2].StaIndexes)
		//fmt.Println("This is the return", id)
		if id >= 0 {
			//fmt.Println("add dispatch.Assigns[a2]")
			if !dispatch.Assigns[a2].AddShip(id, ori, des) {

				continue

			}
			//fmt.Println(dispatch.Assigns[a1])
			dispatch.Assigns[a2].GenRoute()
			//fmt.Println(dispatch.Assigns[a2].StaIndexes)
			if dispatch.Assigns[a2].Cost >= 0 {
				//fmt.Println("passing dispatch.Assigns[a2], remove dispatch.Assigns[a1]")
				dispatch.Assigns[a1].RemoveShip(id)
				dispatch.Assigns[a1].GenRoute()
				if math.Exp((ori_cost-dispatch.Assigns[a1].Cost-dispatch.Assigns[a2].Cost)/temperature) < rand.Float64() {
					dispatch.Assigns[a1].AddShip(id, ori, des)
					dispatch.Assigns[a1].GenRoute()
					dispatch.Assigns[a2].RemoveShip(id)
					dispatch.Assigns[a2].GenRoute()
				}
			} else {
				dispatch.Assigns[a2].RemoveShip(id)
				dispatch.Assigns[a2].GenRoute()
			}
		}
		delta += dispatch.Assigns[a1].Cost + dispatch.Assigns[a2].Cost - ori_cost
		if delta < best_delta {
			best_delta = delta
			best_dispatch = dispatch
		}
	}
	dispatch.RenewnTotalCost()
	return best_dispatch
}

// 输入数据的格式，随时可能会更改
type Batch struct {
	Ready int       `json:"timeReady"`
	Ori   []Station `json:"ori"`
	Des   []Station `json:"des"`
}
type InputData struct {
	LoadCap    int     `json:"loadCap"`
	VehicleNum int     `json:"vehicleNum"`
	Batch      []Batch `json:"batch"`
}

func checkDispatch(dispatch *Dispatch) {
	for ii := 0; ii < dispatch.AssignsLen; ii++ {
		fmt.Println(dispatch.Assigns[ii].StationsLen, dispatch.Assigns[ii].StaIndexesLen, dispatch.Assigns[ii].Stations)
	}
}

// MANAGER
type Memory struct {
	Dispatches [MEMORYSIZE]Dispatch
	ShipCount  int
	Best       int //最佳订单所在位置
	Status     int //记录解是不是空的 0 1
	Stamp      int //记录发生修改订单的event的发生次数
}

type Event struct {
	Type int       // 0: insertion, 1: arrival
	Time int       // Event occuring time
	Oris []Station // 传入的新订单
	Dess []Station // 传入的新订单
}

type EventOutput struct {
	Targets       [MAXASSIGNS]Station `json:"targets"` //记录有每辆车的下一个站点
	TargetsStatus [MAXASSIGNS]int8
	NextTime      int
}

type WorkInsIn struct {
	// this is the insertion event
	Shuttle
	Oris      [MAXINSERTION]Station
	Dess      [MAXINSERTION]Station
	InsLen    int
	TotalShip int
}

type WorkOptIn struct {
	// this is the insertion event
	Shuttle
	Oris      [MAXINSERTION]Station
	Dess      [MAXINSERTION]Station
	InsLen    int
	TotalShip int
}

type Shuttle struct {
	Dispatch    Dispatch
	HelperValue int
	Temperature float64
}

// in_ch 插入事件的chan， result_ch输出的chanel，如果阻塞则停止
func GoInsertShips(in_ch chan *WorkInsIn, out_ch chan *Shuttle) {
	var result Shuttle
	// TODO: 初始化所有的解状态都为1，然后插入只能插入状态为1的解中
	ins := <-in_ch
	result.Dispatch = InsertShips(ins.Dispatch, ins.Oris[:ins.InsLen], ins.Dess[:ins.InsLen], ins.TotalShip)
	result.HelperValue = ins.HelperValue
	out_ch <- &result
}

func GoOptimization(in_ch chan *Shuttle, out_ch chan *Shuttle) {
	//TODO: 解决新事件产生后解前后不兼容的问题
	//logger := zap.L().Named("Simulator")
	time.Sleep(time.Second / 10)
	in := <-in_ch
	//logger.Debug("Got Dispatch")
	in.Dispatch = Optimization(in.Dispatch, in.Temperature)
	//logger.Debug("Got opt result")
	out_ch <- in
	//logger.Debug("pushing  opt result")
}

// 选择适合优化的解
func (mem *Memory) PrepareDispatch() *Shuttle {
	//想法是只循环一遍，累加判断有没有随机到
	var ind int = -1
	var total_weight float64 = 0
	var preceding_weight float64 = 0
	var temperature float64
	var remains int = 0
	logger := zap.L().Named("Manager")
	prob := rand.Float64()
	//fmt.Println("prob", prob, mem.Status)
	for ii := 0; ii < MEMORYSIZE; ii++ {
		if SttChk(mem.Status, ii) {
			total_weight += mem.Dispatches[ii].TotalCost
			//增加记录非空解的数量
			remains += 1
		}
	}
	for ii := 0; ii < MEMORYSIZE; ii++ {
		if SttChk(mem.Status, ii) {
			// 如果前序重量小于概率,要求前序重量恰好大于概率
			preceding_weight += mem.Dispatches[ii].TotalCost
			if preceding_weight/total_weight > prob {
				ind = ii
				break
			}
		}
	}
	// 针对初始化的情况
	if total_weight == 0 {
		ind = mem.Best
		// TODO: 排除所有的解都为零解的情况
	}
	if ind == -1 {
		logger.Warn("non-avaliable in memory, preparing 0")
		ind = 0
	}
	if !SttChk(mem.Status, ind) {
		logger.Warn("preparied non-avaliable solution")
	}
	temperature = float64(HEAT_MAX) * (1.0 - float64(remains)/float64(MEMORYSIZE))
	return &Shuttle{Dispatch: mem.Dispatches[ind], HelperValue: mem.Stamp, Temperature: temperature}
}

func SttChk(x, pos int) bool {
	return x>>pos&1 == 1
}

// 共享accumulated cost XXX: 临时函数
func (mem *Memory) TransAccumulates() {
	for ii := 0; ii < MEMORYSIZE; ii++ {
		for jj := 0; jj < MAXASSIGNS; jj++ {
			mem.Dispatches[ii].Assigns[jj].AccumulatedCost = mem.Dispatches[mem.Best].Assigns[jj].AccumulatedCost
		}
	}
}

func (mem *Memory) Manager(event_ich chan Event, event_och chan EventOutput) {
	var output EventOutput
	var tmp_assign *Assign

	var RESPONSE_COUNT int = 0
	var RESPONSE_TIME time.Duration = 0
	var temp_time time.Time

	var tmp_insi WorkInsIn
	var shuttle *Shuttle

	var prepared_shuttle *Shuttle

	// variable for optimization
	var ind int

	// input and output channel for insertion task
	ins_ich := make(chan *WorkInsIn, MEMORYSIZE)
	ins_och := make(chan *Shuttle, MEMORYSIZE)
	// input and output channel for optimization task
	opt_ich := make(chan *Shuttle, runtime.NumCPU())
	opt_och := make(chan *Shuttle, 1)
	logger := zap.L().Named("Manager")

	prepared_shuttle = mem.PrepareDispatch()

	for {
		select {
		//当获得event信息时
		case event := <-event_ich:
			logger.Info(
				"Getting event",
				zap.Int("type", event.Type),
				zap.Int("time", event.Time),
			)
			//fmt.Println(event)
			if event.Type < 0 {
				fmt.Println(RESPONSE_COUNT, RESPONSE_TIME)
				return
			}
			if event.Type == 0 {
				temp_time = time.Now()
				_time_test_flag := true
				logger.Info(
					"Handling inserting",
				)
				//insertion event
				for ii := range mem.Dispatches {
					if !SttChk(mem.Status, ii) {
						continue
					}
					copy(tmp_insi.Oris[:len(event.Oris)], event.Oris)
					copy(tmp_insi.Dess[:len(event.Dess)], event.Dess)
					tmp_insi.InsLen = len(event.Oris)
					tmp_insi.Dispatch = mem.Dispatches[ii]
					tmp_insi.HelperValue = ii
					insi_copy := tmp_insi

					ins_ich <- &insi_copy
					go GoInsertShips(ins_ich, ins_och)
				}
				logger.Debug("insertion task distributed")
				//获得所有event的执行情况
				for ii := range mem.Dispatches {
					if !SttChk(mem.Status, ii) {
						continue
					}
					//这里必须要等到所有insertion完成
					logger.Debug("getting shuttle")
					shuttle = <-ins_och
					logger.Debug(
						"shuttle got",
						zap.Float64("TotalCost", shuttle.Dispatch.TotalCost),
					)
					mem.Dispatches[shuttle.HelperValue] = shuttle.Dispatch
					if _time_test_flag {
						RESPONSE_TIME += time.Now().Sub(temp_time)
						_time_test_flag = false
					}
				}
				mem.ShipCount += len(event.Oris)
				tmp_insi.TotalShip = mem.ShipCount
				logger.Info(
					"insertion complete",
				)
				RESPONSE_COUNT += 1
			} else {
				logger.Info(
					"Handling Triggering",
				)
				//arrival event
				//标记最优解,记录到达情况
				mem.Dispatches[mem.Best].TriggerTime(event.Time)
				for jj := 0; jj < mem.Dispatches[mem.Best].AssignsLen; jj++ {
					tmp_assign = &mem.Dispatches[mem.Best].Assigns[jj]
					if tmp_assign.Cost >= 0 {
						output.Targets[jj] = tmp_assign.StationCurrent
						output.TargetsStatus[jj] = 1
					}
				}
				//记录不兼容的解并标记为空
				for ii := range mem.Dispatches {
					// 跳过自己和空解
					if (ii == mem.Best) || !SttChk(mem.Status, ii) {
						continue
					}
					//选择不兼容的
					for jj := 0; jj < mem.Dispatches[ii].AssignsLen; jj++ {
						next := mem.Dispatches[ii].Assigns[jj].NextSta
						//如果此辆车为空则跳过
						if mem.Dispatches[mem.Best].Assigns[jj].NextSta == -1 {
							continue
						}
						//检查其它车辆
						if next > -1 && mem.Dispatches[mem.Best].Assigns[jj].StationCurrent.Equal(
							&mem.Dispatches[ii].Assigns[jj].Stations[next],
						) {
							//触发到达
							mem.Dispatches[ii].Assigns[jj].TriggerTime(event.Time)
						} else {
							// 标记为空
							mem.Status -= 1 << ii
							break
						}
					}
				}
			}
			output.NextTime = mem.HelperGetTime()
			logger.Debug(
				"executing pushing output",
			)
			event_och <- output
			logger.Debug(
				"pushing output complete",
			)
			//mem.HelperCheck()
			//活动EVENT之后必须要更新prepared_dispatch
			mem.Stamp += 1
			prepared_shuttle = mem.PrepareDispatch()
			logger.Info(
				"Triggering Complete",
			)
		case shuttle = <-opt_och:
			//replace the worst solutions here
			//如果时间戳不一致那么就放弃
			logger.Debug("Getting optimized dispatch")
			mem.TransAccumulates()
			if shuttle.HelperValue == mem.Stamp {
				ind = mem.Best
				for ii := 0; ii < MEMORYSIZE; ii++ {
					// 如果该解位是不可行解位置那么直接变成改解位置
					if mem.Status>>ii&1 == 0 {
						ind = ii
						mem.Status += 1 << ii //顺便标记改调度为有效调度
						break
					} else {
						// 处理掉最差的解
						if mem.Dispatches[ii].TotalCost > mem.Dispatches[ind].TotalCost {
							ind = ii
						}
					}
				}
				//fmt.Println("Gerring", shuttle.Dispatch.AccumulatedCost, ind)
				mem.Dispatches[ind] = shuttle.Dispatch
				//fmt.Println(shuttle.Dispatch.AccumulatedCost, mem.Dispatches[mem.Best].AccumulatedCost)
				//更新最优解
				if shuttle.Dispatch.TotalCost < mem.Dispatches[mem.Best].TotalCost {
					mem.Best = ind
				}
			} else {
				logger.Debug("discard outdated dispatch")
			}
		case opt_ich <- prepared_shuttle:
			logger.Debug("Pushed optimization task")
			go GoOptimization(opt_ich, opt_och)
			prepared_shuttle = mem.PrepareDispatch()
		default:
			logger.Debug("No event, sleep 1s")
			time.Sleep(time.Millisecond)
		}
	}
}

func (mem *Memory) HelperGetTime() int {
	var next_time int = -1
	var tmp_assign *Assign

	for ii := 0; ii < MEMORYSIZE; ii++ {
		if (mem.Status>>ii)&1 == 0 {
			continue
		}
		for jj := 0; jj < mem.Dispatches[ii].AssignsLen; jj++ {
			tmp_assign = &mem.Dispatches[ii].Assigns[jj]
			if tmp_assign.StationsLen > 0 {
				if next_time < 0 {
					next_time = tmp_assign.TimeCurrent
				} else {
					if next_time > tmp_assign.TimeCurrent {
						next_time = tmp_assign.TimeCurrent
					}
				}
			}
		}
	}
	return next_time
}

func (mem *Memory) HelperCheck() {
	var tmp_assign *Assign
	fmt.Println("=================")
	for ii := 0; ii < MEMORYSIZE; ii++ {
		if mem.Status<<ii&1 == 0 {
			continue
		}
		fmt.Println("dispatch:", ii)
		for jj := 0; jj < mem.Dispatches[ii].AssignsLen; jj++ {
			tmp_assign = &mem.Dispatches[ii].Assigns[jj]
			fmt.Println(tmp_assign.TimeCurrent, tmp_assign.Route[0].CurTime, tmp_assign.Route[0])
		}
	}
}

func h2pSimulation(input_data *InputData, e_ich chan Event, e_och chan EventOutput, sim_time_multi int) {
	var event Event

	var next_time int = 0
	var pre_time int = 0
	var tmp_count int = 0
	var event_output EventOutput
	sim_time := time.Millisecond * time.Duration(sim_time_multi)

	logger := zap.L().Named("Simulator")

	// TODO: 解决有些情况下插入错误的情况
	for ii := range input_data.Batch {
		logger.Info(
			"New batch",
			zap.Int("ready_time", input_data.Batch[ii].Ready),
		)
		tmp_count = 0
		// 把当前时间点之前的到达操作全部都执行完
		for next_time > -1 && next_time <= input_data.Batch[ii].Ready && tmp_count <= 1000 {
			tmp_count += 1
			logger.Debug(
				"triger iteration",
				zap.Int("iter", ii),
				zap.Int("trigger", tmp_count),
				zap.Int("time", next_time),
				zap.Int("sleep:", next_time-pre_time),
			)
			if next_time > -1 {
				fmt.Println(next_time, pre_time, tmp_count)
				time.Sleep(time.Duration(next_time - pre_time))
				event.Type = 1
				event.Time = next_time
				logger.Debug("Pushing Event")
				e_ich <- event
				event_output = <-e_och
				logger.Debug("Got Event")
				pre_time = next_time
				next_time = event_output.NextTime
			}
		}
		// 当next_time > ready_time 的时候应当先休眠到ready_time
		if input_data.Batch[ii].Ready > pre_time {
			time.Sleep(time.Duration(input_data.Batch[ii].Ready-pre_time) * sim_time)
		}
		//执行插入事件
		event.Oris = input_data.Batch[ii].Ori
		event.Dess = input_data.Batch[ii].Des
		event.Type = 0
		e_ich <- event
		<-e_och
		next_time = input_data.Batch[ii].Ready
	}
	//此时下一段时间应当交给下一批次执行
	time.Sleep(time.Duration(next_time-pre_time) * sim_time)
	//结束
	logger.Info(
		"ENDDING",
	)
	event.Type = -1
	e_ich <- event
}

func init() {
	encoderConfig := zap.NewProductionEncoderConfig()
	encoderConfig.EncodeTime = zapcore.ISO8601TimeEncoder
	encoderConfig.EncodeLevel = zapcore.CapitalColorLevelEncoder
	encoder := zapcore.NewConsoleEncoder(encoderConfig)
	writeSyncer := zapcore.AddSync(os.Stdout)
	core := zapcore.NewCore(encoder, writeSyncer, zapcore.WarnLevel)
	logger := zap.New(core)
	zap.ReplaceGlobals(logger)
}

func main() {
	fmt.Println(runtime.NumCPU())
	fmt.Println(os.Args)
	var input_data InputData
	var mem Memory
	var template Assign
	event_ich := make(chan Event, 1)
	event_och := make(chan EventOutput, 1)
	filename := os.Args[1]
	if err := read_json(filename, &input_data); err != nil {
		fmt.Fprintf(os.Stderr, "read_json: %v\n", err)
		os.Exit(1)
	}
	template.LoadCap = input_data.LoadCap
	template.Speed = 1

	// 设置车辆初始位置为depot（从输入数据第一个batch的ori[0]获取）
	if len(input_data.Batch) > 0 && len(input_data.Batch[0].Ori) > 0 {
		template.StationCurrent = input_data.Batch[0].Ori[0]
		template.StationCurrent.Load = 0
		template.StationCurrent.ReqCode = 0
	}

	//初始化前几个解
	for ii := 0; ii < MEMORYSIZE; ii++ {
		mem.Dispatches[ii].Init(template)
	}
	mem.Status = (1 << MEMORYSIZE) - 1
	multi, _ := strconv.Atoi(os.Args[2])
	startWall := time.Now()
	go h2pSimulation(&input_data, event_ich, event_och, multi)
	defer zap.L().Sync()
	mem.Manager(event_ich, event_och)
	var total float64 = 0
	for jj := 0; jj < MAXASSIGNS; jj++ {
		assign := &mem.Dispatches[mem.Best].Assigns[jj]
		total += assign.AccumulatedCost + assign.Cost
		// 对已完成服务的车辆补上回仓距离
		if assign.StationsLen == 0 && assign.AccumulatedCost > 0 {
			total += cal_dis(assign.StationCurrent, template.StationCurrent)
		}
	}
	fmt.Printf("RES %.6f\n", time.Since(startWall).Seconds())
	fmt.Println("final cost", total)
}
